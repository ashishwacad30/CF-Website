from langchain_community.document_loaders import PyPDFLoader, UnstructuredExcelLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS

def generate_vectorstore():
    pdf_path = "/Users/ashish/Downloads/Agentic-AI/NNC - NNC RECIPIENTS PROGRAM MANUAL - 2023_24 (EN).pdf"
    pdf_loader = PyPDFLoader(pdf_path)
    pdf_pages = pdf_loader.load()
    print(f"Loaded {len(pdf_pages)} PDF pages")

    print("\nChecking loaded PDF content:")
    for i, page in enumerate(pdf_pages):
        if "All frozen French fries" in page.page_content:
            print(f"Found 'All frozen French fries' on page {i}:\n{page.page_content[:500]}\n")

    # excel_path = "/Users/ashish/Downloads/Agentic-AI/NNC Eligibility List - Liste produits Ã©ligibles JAN2023.xlsx"  # 🧾 Replace with your actual path
    # excel_loader = UnstructuredExcelLoader(excel_path)
    # excel_rows = excel_loader.load()
    # print(f"Loaded {len(excel_rows)} rows from Excel")

    all_docs = pdf_pages 

    splitter = RecursiveCharacterTextSplitter(chunk_size=500, chunk_overlap=100)
    chunks = splitter.split_documents(all_docs)

    if not chunks:
        raise ValueError("No extractable content found in PDF/Excel.")

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
