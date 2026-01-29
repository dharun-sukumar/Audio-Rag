from langchain_chroma import Chroma
from langchain_huggingface import HuggingFaceEmbeddings
from app.core.config import DB_DIR

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = Chroma(
    persist_directory=DB_DIR,
    embedding_function=embeddings
)

def add_chunks(chunks, source, filename, uploaded_at, date):
    texts = []
    metadatas = []

    for c in chunks:
        texts.append(c["text"])
        metadatas.append({
            "source": source,
            "filename": filename,
            "uploaded_at": uploaded_at,
            "date": date,
            "start": c.get("start"),
            "end": c.get("end"),
        })

    vectorstore.add_texts(texts, metadatas=metadatas)
