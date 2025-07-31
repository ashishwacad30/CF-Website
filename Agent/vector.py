from langchain_community.document_loaders import PyPDFLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain.docstore.document import Document
import re

def extract_semantic_chunks_with_metadata(pdf_path):
    from PyPDF2 import PdfReader
    reader = PdfReader(pdf_path)
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
                # Save previous chunk
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
    pdf_path = "/Users/ashish/Downloads/Agentic-AI/NNC - NNC RECIPIENTS PROGRAM MANUAL - 2023_24 (EN) (1).pdf"
    pdf_loader = PyPDFLoader(pdf_path)
    pdf_pages = pdf_loader.load()
    print(f"Loaded {len(pdf_pages)} PDF pages")

    print("\nChecking loaded PDF content:")
    for i, page in enumerate(pdf_pages):
        if "All frozen French fries" in page.page_content:
            print(f"Found 'All frozen French fries' on page {i}:\n{page.page_content[:500]}\n")

    all_docs = pdf_pages

    semantic_chunks = extract_semantic_chunks_with_metadata(pdf_path)

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    recursive_chunks = splitter.split_documents(all_docs)

    for i, doc in enumerate(recursive_chunks):
        doc.metadata = {**doc.metadata, "source": "recursive", "recursive_idx": i}

    chunks = semantic_chunks + recursive_chunks

    if not chunks:
        raise ValueError("No extractable content found in PDF.")

    print(f"Total Chunks: {len(chunks)}")
    for i, doc in enumerate(chunks):
        if "All frozen French fries" in doc.page_content:
            print(f"Chunk {i} contains match:\n{doc.page_content}\n")

    embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(chunks, embedding_model)
    vectorstore.save_local("product_agent_index")
    print("Vectorstore saved as 'product_agent_index'")

if __name__ == "__main__":
    generate_vectorstore()