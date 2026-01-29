from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from langchain_huggingface import HuggingFaceEmbeddings

# Initialize embeddings model once
embeddings_model = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

def add_chunks(
    db: Session,
    user: User,
    chunks: list,
    source: str,
    filename: str
):
    # 1. Create Document record
    doc = Document(
        user_id=user.id,
        filename=filename,
        source_key=source
    )
    db.add(doc)
    db.flush() # flush to get doc.id

    # 2. Prepare Chunk records
    chunk_objects = []
    
    # Batch compute embeddings for efficiency
    texts = [c["text"] for c in chunks]
    vectors = embeddings_model.embed_documents(texts)

    for i, c in enumerate(chunks):
        chunk = Chunk(
            document_id=doc.id,
            user_id=user.id,
            content=c["text"],
            embedding=vectors[i]
        )
        chunk_objects.append(chunk)

    # 3. Bulk insert chunks
    db.add_all(chunk_objects)
    db.commit()
    
    return doc.id
