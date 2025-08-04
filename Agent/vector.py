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
from dotenv import load_dotenv
from PyPDF2 import PdfReader
from tempfile import NamedTemporaryFile
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain_community.document_loaders import PyPDFLoader
from langchain_huggingface import HuggingFaceEmbeddings  # updated import
from langchain.docstore.document import Document

load_dotenv(dotenv_path=".env")

def extract_semantic_chunks_with_metadata(pdf_stream):
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

def embeddings_exist(base_name):
    return os.path.exists(base_name)

def generate_vectorstore():
    bucket_name = os.getenv("BUCKET_NAME")
    object_key = os.getenv("OBJECT_KEY")
    print("Loaded OBJECT_KEY:", object_key)

    base_name = "product_agent_index"  # Consistent folder name for saving/loading

    if embeddings_exist(base_name):
        print(f"Embeddings already exist for: {base_name}. Skipping generation.")
        return

    os.makedirs(base_name, exist_ok=True)

    # Download PDF from S3
    s3 = boto3.client("s3")
    pdf_stream = BytesIO()
    s3.download_fileobj(bucket_name, object_key, pdf_stream)
    pdf_stream.seek(0)

    # Save PDF temporarily for PyPDFLoader
    with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_pdf:
        tmp_pdf.write(pdf_stream.read())
        tmp_pdf_path = tmp_pdf.name

    pdf_stream.seek(0)

    # Load PDF pages with LangChain loader
    pdf_loader = PyPDFLoader(file_path=tmp_pdf_path)
    pdf_pages = pdf_loader.load()
    print(f"Loaded {len(pdf_pages)} PDF pages")

    # Extract semantic chunks with metadata
    semantic_chunks = extract_semantic_chunks_with_metadata(pdf_stream)

    # Use RecursiveCharacterTextSplitter for recursive chunks
    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    recursive_chunks = splitter.split_documents(pdf_pages)

    # Add metadata to recursive chunks
    for i, doc in enumerate(recursive_chunks):
        doc.metadata = {**doc.metadata, "source": "recursive", "recursive_idx": i}

    # Combine chunks
    chunks = semantic_chunks + recursive_chunks

    if not chunks:
        raise ValueError("No extractable content found in PDF.")

    print(f"Total Chunks: {len(chunks)}")

    # Initialize embedding model
    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")

    # Create vectorstore from documents
    vectorstore = FAISS.from_documents(chunks, embedding_model)

    # Save vectorstore locally in the base_name folder
    vectorstore.save_local(base_name)
    print(f"Vectorstore saved as '{base_name}'")

if __name__ == "__main__":
    generate_vectorstore()