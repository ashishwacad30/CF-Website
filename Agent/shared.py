import os
import json
from pathlib import Path
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings  # updated import
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader
import weaviate
from weaviate.auth import AuthApiKey
from urllib.parse import urlparse
from langchain.docstore.document import Document
from weaviate import Client as V3Client
import time
from typing import Optional
import requests

dotenv_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=dotenv_path)
os.environ["TOKENIZERS_PARALLELISM"] = "false"
GROQ_API_KEY = os.getenv("GROQ_API_KEY")

# print("From Python:", GROQ_API_KEY)
# load_dotenv(dotenv_path=".env")
# os.environ["TOKENIZERS_PARALLELISM"] = "false"

# GROQ_API_KEY = os.getenv("GROQ_API_KEY")
# print("From Python:", GROQ_API_KEY)

EMBEDDINGS_MODEL_NAME = os.getenv("EMBEDDINGS_MODEL_NAME", "sentence-transformers/all-mpnet-base-v2")
embedding_model = HuggingFaceEmbeddings(model_name=EMBEDDINGS_MODEL_NAME)

WEAVIATE_HOST = os.getenv("WEAVIATE_HOST", "http://localhost:8080")
WEAVIATE_API_KEY = os.getenv("WEAVIATE_API_KEY") or None
WEAVIATE_CLASS_NAME = os.getenv("WEAVIATE_CLASS_NAME", "ProductChunk")
WEAVIATE_STARTUP_TIMEOUT_SECONDS = int(os.getenv("WEAVIATE_STARTUP_TIMEOUT_SECONDS", "5"))

parsed = urlparse(WEAVIATE_HOST)
http_host = parsed.hostname or "localhost"
http_port = parsed.port or (443 if (parsed.scheme or "http") == "https" else 8080)
http_secure = (parsed.scheme or "http") == "https"
grpc_host = http_host
grpc_port = int(os.getenv("WEAVIATE_GRPC_PORT", "50051"))
grpc_secure = http_secure

_weaviate_client: Optional[V3Client] = None

def _weaviate_ready(url: str, timeout: float = 1.0) -> bool:
	"""HTTP readiness probe compatible with Weaviate v1 REST readiness endpoint."""
	probe = url.rstrip("/") + "/v1/.well-known/ready"
	try:
		resp = requests.get(probe, timeout=timeout)
		return resp.status_code == 200
	except Exception:
		return False

def get_weaviate_client(force: bool = False) -> Optional[V3Client]:
	"""Create or return a cached Weaviate V3 client.
    Delays creation until first use and tolerates temporary startup unavailability
    by retrying for WEAVIATE_STARTUP_TIMEOUT_SECONDS.
    Returns None if unreachable after retries so callers can degrade gracefully.
    """
	global _weaviate_client
	if _weaviate_client is not None and not force:
		return _weaviate_client

	deadline = time.time() + WEAVIATE_STARTUP_TIMEOUT_SECONDS
	last_err: Optional[Exception] = None
	while time.time() < deadline:
		try:
			client = V3Client(
				url=WEAVIATE_HOST,
				auth_client_secret=AuthApiKey(WEAVIATE_API_KEY) if WEAVIATE_API_KEY else None,
			)
			if _weaviate_ready(WEAVIATE_HOST, timeout=1.0):
				_weaviate_client = client
				return _weaviate_client
		except Exception as e:
			last_err = e
			time.sleep(0.5)
		else:
			# not ready yet
			time.sleep(0.5)

	print(f"Weaviate client unavailable at {WEAVIATE_HOST}: {last_err}")
	_weaviate_client = None
	return None

class WeaviateV3VectorStore:
	def __init__(self, client_provider, embedding: object, index_name: str, text_key: str = "text"):
		self._client_provider = client_provider  # callable returning client or None
		self.embedding = embedding
		self.index_name = index_name
		self.text_key = text_key

	def _get_client_or_none(self) -> Optional[V3Client]:
		return self._client_provider()

	def similarity_search(self, query: str, k: int = 5):
		client = self._get_client_or_none()
		if client is None:
			return []

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
		try:
			vec_resp = (
				client.query.get(self.index_name, props)
				.with_near_vector({"vector": query_vector})
				.with_additional(["distance", "id"])  # include id to help de-dup
				.with_limit(k)
				.do()
			)
			vec_items = vec_resp.get("data", {}).get("Get", {}).get(self.index_name, [])
		except Exception:
			vec_items = []

		try:
			bm25_resp = (
				client.query.get(self.index_name, props)
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
	client_provider=lambda: get_weaviate_client(),
	embedding=embedding_model,
	index_name=WEAVIATE_CLASS_NAME,
	text_key="text",
)

llm = ChatGroq(model_name="llama-3.3-70b-versatile", api_key=GROQ_API_KEY, temperature=0)

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