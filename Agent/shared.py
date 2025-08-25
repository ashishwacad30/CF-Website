import os
import json
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings  # updated import
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader
import weaviate
from weaviate.auth import AuthApiKey
from urllib.parse import urlparse
from langchain.docstore.document import Document

load_dotenv(dotenv_path=".env")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# Embedding model (must match the one used to ingest into Weaviate)
EMBEDDINGS_MODEL_NAME = os.getenv("EMBEDDINGS_MODEL_NAME", "sentence-transformers/all-mpnet-base-v2")
embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL_NAME)

# Weaviate vector store
WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY") or None
WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME", "ProductChunk")

parsed = urlparse(WEAVIATE_HOST)
http_host = parsed.hostname or "localhost"
http_port = parsed.port or (443 if (parsed.scheme or "http") == "https" else 8080)
http_secure = (parsed.scheme or "http") == "https"
grpc_host = http_host
grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
grpc_secure = http_secure

# v3 client (REST-only)
from weaviate import Client as V3Client  # type: ignore
if WEAVIATE_API_KEY:
    weaviate_client = V3Client(url=WEAVIATE_HOST, auth_client_secret=AuthApiKey(WEAVIATE_API_KEY))
else:
    weaviate_client = V3Client(url=WEAVIATE_HOST)


class WeaviateV3VectorStore:
    def __init__(self, client: V3Client, embedding: object, index_name: str, text_key: str = "text"):
        self.client = client
        self.embedding = embedding
        self.index_name = index_name
        self.text_key = text_key

    def similarity_search(self, query: str, k: int = 5):
        query_vector = self.embedding.embed_query(query)
        props = [
            self.text_key,
            "page",
            "product_code",
            "category",
            "source",
            "recursive_idx",
        ]
        # Vector search
        vec_resp = (
            self.client.query.get(self.index_name, props)
            .with_near_vector({"vector": query_vector})
            .with_additional(["distance", "id"])  # include id to help de-dup
            .with_limit(k)
            .do()
        )
        vec_items = vec_resp.get("data", {}).get("Get", {}).get(self.index_name, [])

        # BM25 fallback (text relevance)
        try:
            bm25_resp = (
                self.client.query.get(self.index_name, props)
                .with_bm25(query=query)
                .with_additional(["score", "id"])  # include id to help de-dup
                .with_limit(k)
                .do()
            )
            bm25_items = bm25_resp.get("data", {}).get("Get", {}).get(self.index_name, [])
        except Exception:
            bm25_items = []

        # Merge: prefer vector results; fill remaining with BM25 uniques
        by_id = {}
        ordered = []
        for obj in vec_items:
            obj_id = obj.get("_additional", {}).get("id")
            if obj_id and obj_id not in by_id:
                by_id[obj_id] = obj
                ordered.append(obj)
        for obj in bm25_items:
            obj_id = obj.get("_additional", {}).get("id")
            if obj_id and obj_id not in by_id:
                by_id[obj_id] = obj
                ordered.append(obj)
                if len(ordered) >= k:
                    break

        documents = []
        for obj in ordered[:k]:
            content = obj.get(self.text_key, "")
            metadata = {
                "page": obj.get("page"),
                "product_code": obj.get("product_code"),
                "category": obj.get("category"),
                "source": obj.get("source"),
                "recursive_idx": obj.get("recursive_idx"),
            }
            documents.append(Document(page_content=content, metadata=metadata))
        return documents


vectorstore = WeaviateV3VectorStore(
    client=weaviate_client,
    embedding=embedding_model,
    index_name=WEAVIATE_CLASS_NAME,
    text_key="text",
)

llm = ChatGroq(model_name="llama-3.3-70b-versatile", api_key=GROQ_API_KEY)

def get_pdf_text(pdf_path: str) -> str:
    try:
        reader = PdfReader(pdf_path)
        return "".join(page.extract_text() for page in reader.pages if page.extract_text())
    except Exception as e:
        print(f"Error reading PDF: {e}")
        return ""

def query_llm(prompt: str) -> str:
    response = llm.invoke(prompt)
    return response.content.strip()