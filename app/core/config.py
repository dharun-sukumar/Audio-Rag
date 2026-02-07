import os
from dotenv import load_dotenv

load_dotenv()

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
LLM_MODEL = os.getenv("LLM_MODEL", "llama-3.1-8b-instant")
ASSEMBLYAI_API_KEY = os.getenv("ASSEMBLYAI_API_KEY")
ACCESS_KEY = os.getenv("ACCESS_KEY")
SECRET_KEY= os.getenv("SECRET_KEY")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")



BUCKET = "hiffi"
REGION = "blr1"
ENDPOINT = "https://blr1.digitaloceanspaces.com"

DB_DIR = "./chroma_db"
