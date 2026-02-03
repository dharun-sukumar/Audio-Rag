from langchain_groq import ChatGroq
from langchain_core.messages import SystemMessage, HumanMessage
from sqlalchemy.orm import Session
from sqlalchemy import text
from app.core.config import GROQ_API_KEY, LLM_MODEL
from app.models.chunk import Chunk
from app.models.user import User
from app.services.vectorstore import embeddings_model
from app.services.utils import is_date_question

SYSTEM_PROMPT = """You are an action-oriented assistant for this memory platform.

You do NOT provide general advice, explanations, or educational content.
You exist ONLY to help users take actions inside this app.

HARD RULES (NO EXCEPTIONS)
- Do NOT answer general questions (health, life advice, definitions, how-to guides).
- Do NOT provide tips, explanations, or instructions unrelated to app actions.
- Do NOT behave like a general AI assistant.
- Do NOT answer hypotheticals or abstract questions.

ALLOWED RESPONSES
You may ONLY:
1) Help the user create, view, organize, or query memories
2) Explain what actions are possible inside the app
3) Guide the user to perform a specific app action

MEMORY-DEPENDENT QUESTIONS
- If a question requires a memory and none exists:
  - Do NOT answer the question
  - Redirect the user to create a memory instead

REDIRECTION BEHAVIOR
When a question is outside the app’s scope:
- Gently redirect the user to an app action
- Encourage uploading text, audio, or video
- Explain how the app can help *once a memory exists*

EXAMPLES OF CORRECT REDIRECTION
- “I can help with this once you add it as a memory.”
- “Try recording or writing this as a memory, and we can work with it.”
- “This platform works by analyzing your memories. Add one to get started.”

SOCIAL RULE
- If the user greets you, respond briefly and then guide them to an action.

STYLE
- Short, clear, and direct
- No emojis
- No markdown
- No apologies
- No general knowledge

You are an interface to actions, not a source of advice.
"""

llm = ChatGroq(
    api_key=GROQ_API_KEY,
    model=LLM_MODEL,
    temperature=0
)

def ask(db: Session, user: User, query: str, k=5):
    # 1. Embed query (using vectorstore service's initialized model)
    query_vector = embeddings_model.embed_query(query)

    # 2. Semantic Search in Postgres (pgvector)
    # Allows searching across both Document-based chunks and Memory-based chunks
    chunks = db.query(Chunk).filter(
        Chunk.user_id == user.id
    ).order_by(
        Chunk.embedding.l2_distance(query_vector)
    ).limit(k).all()

    # 3. Construct Context
    context_blocks = [c.content for c in chunks]
    context = "\n\n".join(context_blocks)

    if not context:
        context = "NO_RELEVANT_MEMORY"

    # 4. Generate Answer
    prompt = f"""
{SYSTEM_PROMPT}

Context:
{context}

Question:
{query}
""".strip()

    response = llm.invoke(messages)

    return {
        "answer": response.content.strip()
    }