# import os
# import re
# import boto3
# from io import BytesIO
# from langchain.text_splitter import RecursiveCharacterTextSplitter
# from langchain_community.vectorstores import FAISS
# from langchain_community.document_loaders import PyPDFLoader
# from langchain.docstore.document import Document
# from PyPDF2 import PdfReader
# from tempfile import NamedTemporaryFile
# from dotenv import load_dotenv
# from langchain_huggingface import HuggingFaceEmbeddings

# load_dotenv(dotenv_path=".env")

# def extract_semantic_chunks_with_metadata(pdf_stream):
#     reader = PdfReader(pdf_stream)
#     chunks = []

#     for page_number, page in enumerate(reader.pages):
#         text = page.extract_text()
#         if not text:
#             continue
#         lines = text.splitlines()
#         current_chunk = []
#         current_category = None
#         current_code = None

#         for line in lines:
#             match = re.match(r'^(\d{1,2}-[A-Z0-9]+)\s+(.+)', line.strip())
#             if match:
#                 if current_chunk:
#                     chunks.append(Document(
#                         page_content="\n".join(current_chunk),
#                         metadata={
#                             "page": page_number + 1,
#                             "product_code": current_code,
#                             "category": current_category
#                         }
#                     ))
#                     current_chunk = []

#                 current_code, current_category = match.groups()
#             current_chunk.append(line.strip())

#         if current_chunk:
#             chunks.append(Document(
#                 page_content="\n".join(current_chunk),
#                 metadata={
#                     "page": page_number + 1,
#                     "product_code": current_code,
#                     "category": current_category
#                 }
#             ))

#     return chunks

# def embeddings_exist(base_name):
#     path = os.path.join("vectorstores", base_name)
#     return os.path.exists(path)

# def generate_vectorstore():
#     bucket_name = os.getenv("BUCKET_NAME")
#     object_key = os.getenv("OBJECT_KEY")
#     print("Loaded OBJECT_KEY:", object_key)

#     base_name = os.path.splitext(os.path.basename(object_key))[0]
#     vectorstore_path = os.path.join("vectorstores", base_name)
#     os.makedirs("vectorstores", exist_ok=True)

#     if embeddings_exist(base_name):
#         print(f"Embeddings already exist for: {base_name}. Skipping generation.")
#         return

#     s3 = boto3.client("s3")
#     pdf_stream = BytesIO()
#     s3.download_fileobj(bucket_name, object_key, pdf_stream)
#     pdf_stream.seek(0)

#     # Save PDF temporarily for PyPDFLoader (since it doesn't accept BytesIO)
#     with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
#         tmp_pdf.write(pdf_stream.read())
#         tmp_pdf_path = tmp_pdf.name

#     # Rewind the stream for PyPDF2 (if needed)
#     pdf_stream.seek(0)
#     reader = PdfReader(pdf_stream)

#     # Load using LangChain loader
#     pdf_loader = PyPDFLoader(file_path=tmp_pdf_path)
#     pdf_pages = pdf_loader.load()
#     print(f"Loaded {len(pdf_pages)} PDF pages")

#     print("\nChecking loaded PDF content:")
#     for i, page in enumerate(pdf_pages):
#         if "All frozen French fries" in page.page_content:
#             print(f"Found 'All frozen French fries' on page {i}:\n{page.page_content[:500]}\n")

#     all_docs = pdf_pages

#     pdf_stream.seek(0)
#     semantic_chunks = extract_semantic_chunks_with_metadata(pdf_stream)

#     splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
#     recursive_chunks = splitter.split_documents(all_docs)

#     for i, doc in enumerate(recursive_chunks):
#         doc.metadata = {**doc.metadata, "source": "recursive", "recursive_idx": i}

#     chunks = semantic_chunks + recursive_chunks

#     if not chunks:
#         raise ValueError("No extractable content found in PDF.")

#     print(f"Total Chunks: {len(chunks)}")
#     for i, doc in enumerate(chunks):
#         if "All frozen French fries" in doc.page_content:
#             print(f"Chunk {i} contains match:\n{doc.page_content}\n")

#     embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
#     vectorstore = FAISS.from_documents(chunks, embedding_model)
#     vectorstore.save_local(vectorstore_path)
#     print(f"Vectorstore saved as '{vectorstore_path}'")

# if __name__ == "__main__":
#     generate_vectorstore()


import os
import re
import boto3
from io import BytesIO
from dotenv import load_dotenv, find_dotenv
from PyPDF2 import PdfReader
from tempfile import NamedTemporaryFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings  # updated import
from langchain.docstore.document import Document
from weaviate.auth import AuthApiKey
from weaviate import Client as V3Client

"""Vector ingestion utilities for PDF content into Weaviate.

This module extracts semantically meaningful chunks from a PDF, augments them
with recursive text splitting, embeds with a HuggingFace model, and ingests the
vectors and metadata into a Weaviate cluster.
"""

load_dotenv(find_dotenv())

def extract_semantic_chunks_with_metadata(pdf_stream):
    """Parse a PDF stream into category/code-aware text chunks.

    The function walks each page, identifies lines that start a product
    category/code block, and accumulates lines until the next block. It outputs
    `Document` objects with `page`, `product_code`, and `category` metadata.

    Args:
        pdf_stream: A binary stream positioned at the start of a PDF file.

    Returns:
        A list of `langchain.docstore.document.Document` instances.
    """
    reader = PdfReader(pdf_stream)
    chunks = []

    for page_number, page in enumerate(reader.pages):
        text = page.extract_text()
        if not text:
            continue
        lines = text.splitlines()
        current_chunk = []
        current_category = None
        current_code = None

        for line in lines:
            match = re.match(r'^(\d{1,2}-[A-Z0-9]+)\s+(.+)', line.strip())
            if match:
                if current_chunk:
                    chunks.append(Document(
                        page_content="\n".join(current_chunk),
                        metadata={
                            "page": page_number + 1,
                            "product_code": current_code,
                            "category": current_category
                        }
                    ))
                    current_chunk = []

                current_code, current_category = match.groups()
            current_chunk.append(line.strip())

        if current_chunk:
            chunks.append(Document(
                page_content="\n".join(current_chunk),
                metadata={
                    "page": page_number + 1,
                    "product_code": current_code,
                    "category": current_category
                }
            ))

    return chunks

def generate_vectorstore():
    """Create embeddings for PDF content and ingest into Weaviate.

    - Downloads a PDF from S3 specified by environment variables `BUCKET_NAME`
      and `OBJECT_KEY`.
    - Extracts semantic and recursively split chunks.
    - Embeds chunk texts using `sentence-transformers/all-mpnet-base-v2`.
    - Ensures the Weaviate class exists and batches ingestion with attached
      vectors.
    """
    bucket_name = os.getenv("BUCKET_NAME")
    object_key = os.getenv("OBJECT_KEY")
    print("Loaded OBJECT_KEY:", object_key)

    s3 = boto3.client("s3")
    pdf_stream = BytesIO()
    s3.download_fileobj(bucket_name, object_key, pdf_stream)
    pdf_stream.seek(0)

    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_stream.read())
        tmp_pdf_path = tmp_pdf.name

    pdf_stream.seek(0)

    pdf_loader = PyPDFLoader(file_path=tmp_pdf_path)
    pdf_pages = pdf_loader.load()
    print(f"Loaded {len(pdf_pages)} PDF pages")

    semantic_chunks = extract_semantic_chunks_with_metadata(pdf_stream)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    recursive_chunks = splitter.split_documents(pdf_pages)

    for i, doc in enumerate(recursive_chunks):
        doc.metadata = {**doc.metadata, "source": "recursive", "recursive_idx": i}

    chunks = semantic_chunks + recursive_chunks
    if not chunks:
        raise ValueError("No extractable content found in PDF.")
    print(f"Total Chunks: {len(chunks)}")

    embedding_model = HuggingFaceEmbeddings(model_name="sentence-transformers/all-mpnet-base-v2")

    weaviate_host = os.getenv("WEAVIATE_HOST", "http://localhost:8080")
    weaviate_api_key = os.getenv("WEAVIATE_API_KEY") or None
    class_name = os.getenv("WEAVIATE_CLASS_NAME", "ProductChunk")

    if weaviate_api_key:
        client = V3Client(url=weaviate_host, auth_client_secret=AuthApiKey(weaviate_api_key))
    else:
        client = V3Client(url=weaviate_host)

    try:
        schema = client.schema.get()
        existing_classes = {c.get('class') for c in schema.get('classes', [])}
        if class_name not in existing_classes:
            class_obj = {
                "class": class_name,
                "vectorizer": "none",
                "properties": [
                    {"name": "text", "dataType": ["text"]},
                    {"name": "page", "dataType": ["int"]},
                    {"name": "product_code", "dataType": ["text"]},
                    {"name": "category", "dataType": ["text"]},
                    {"name": "source", "dataType": ["text"]},
                    {"name": "recursive_idx", "dataType": ["int"]},
                ],
            }
            client.schema.create_class(class_obj)
            print(f"Created Weaviate class: {class_name}")
    except Exception as schema_err:
        print(f"Weaviate schema ensure error: {schema_err}")

    texts = [doc.page_content for doc in chunks]
    metadatas = [doc.metadata for doc in chunks]

    vectors = embedding_model.embed_documents(texts)

    client.batch.configure(batch_size=64)
    with client.batch as batch:
        for content, metadata, vector in zip(texts, metadatas, vectors):
            props = {
                "text": content,
                "page": int(metadata.get("page") or 0),
                "product_code": metadata.get("product_code"),
                "category": metadata.get("category"),
                "source": metadata.get("source", "recursive"),
                "recursive_idx": int(metadata.get("recursive_idx") or 0),
            }
            batch.add_data_object(data_object=props, class_name=class_name, vector=vector)

    print(f"Ingested {len(texts)} chunks into Weaviate class '{class_name}'")
if __name__ == "__main__":
    generate_vectorstore()