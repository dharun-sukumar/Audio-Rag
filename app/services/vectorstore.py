from sqlalchemy.orm import Session
from app.models.document import Document
from app.models.chunk import Chunk
from app.models.user import User
from app.models.memory import Memory
from langchain_openai import OpenAIEmbeddings
from app.core.config import OPENAI_API_KEY
from typing import List, Optional
from uuid import UUID

# Initialize embeddings model once
embeddings_model = OpenAIEmbeddings(
    model="text-embedding-3-large",
    api_key=OPENAI_API_KEY
)

def add_chunks(
    db: Session,
    user: User,
    chunks: list,
    source: str,
    filename: str,
    status: str = "indexed",
    transcript_key: str = None
):
    # 1. Create Document record
    doc = Document(
        user_id=user.id,
        filename=filename,
        source_key=source,
        transcript_key=transcript_key,
        status=status
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


def add_memory_chunks(
    db: Session,
    user_id: UUID,
    memory_id: UUID,
    text_chunks: List[str]
):
    """
    Generate embeddings for text chunks and save them linked to a memory.
    """
    if not text_chunks:
        return

    # Batch compute embeddings
    vectors = embeddings_model.embed_documents(text_chunks)
    
    chunk_objects = []
    for i, text in enumerate(text_chunks):
        chunk = Chunk(
            memory_id=memory_id,
            user_id=user_id,
            content=text,
            embedding=vectors[i]
        )
        chunk_objects.append(chunk)
    
    db.add_all(chunk_objects)
    db.commit()
