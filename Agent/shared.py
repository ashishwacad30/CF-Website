import os
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import FAISS
from langchain_groq import ChatGroq
from PyPDF2 import PdfReader

load_dotenv(dotenv_path=".env")
os.environ["TOKENIZERS_PARALLELISM"] = "false"

GROQ_API_KEY = os.getenv("GROQ_API_KEY")

embedding_model = HuggingFaceEmbeddings(model_name="all-MiniLM-L6-v2")
vectorstore = FAISS.load_local("product_agent_index", embedding_model, allow_dangerous_deserialization=True)
llm = ChatGroq(model_name="llama3-70b-8192", api_key=GROQ_API_KEY)

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