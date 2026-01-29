from langchain_groq import ChatGroq
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import GROQ_API_KEY
from app.models.chunk import Chunk
from app.models.user import User
from app.services.vectorstore import embeddings_model
from app.services.utils import is_date_question

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model="llama-3.1-8b-instant",
    temperature=0.2
)

def ask(db: Session, user: User, query: str, k=5):
    # 1. Embed query
    query_vector = embeddings_model.embed_query(query)

    # 2. Semantic Search in Postgres (pgvector)
    # The <-> operator is L2 distance. Order by distance ASC (closest first).
    chunks = db.query(Chunk).filter(
        Chunk.user_id == user.id
    ).order_by(
        Chunk.embedding.l2_distance(query_vector)
    ).limit(k).all()

    # 3. Construct Context
    context_blocks = [c.content for c in chunks]
    context = "\n\n".join(context_blocks)

    if not context:
        return {"answer": "I couldn't find any relevant information in your uploaded documents."}

    # 4. Generate Answer
    prompt = f"""
You are answering questions using retrieved transcript content.

RULES:
- Do NOT invent facts.
- Use ONLY the provided context.
- If the answer is not in the context, say so.

Context:
{context}

Question:
{query}

Answer:
""".strip()

    response = llm.invoke(prompt)

    return {
        "answer": response.content.strip()
    }