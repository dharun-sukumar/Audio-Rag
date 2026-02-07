import json
from datetime import datetime
from uuid import UUID
from typing import List, Optional, Dict, Any

from sqlalchemy.orm import Session
from sqlalchemy import text, desc, func
from langchain_groq import ChatGroq
from langchain_text_splitters import RecursiveCharacterTextSplitter

from app.core.config import GROQ_API_KEY, LLM_MODEL
from app.models.user import User
from app.models.memory import SemanticMemory, EntityMemory, Memory, MediaType, ProcessingStatus
from app.services.vectorstore import embeddings_model, add_memory_chunks
from app.services.memory_service import MemoryService
from app.schemas.memory import MemoryCreate

# --- CONFIGURATION ---
llm_compiler = ChatGroq(
    api_key=GROQ_API_KEY,
    model=LLM_MODEL,
    temperature=0.0
)

llm_responder = ChatGroq(
    api_key=GROQ_API_KEY,
    model=LLM_MODEL,
    temperature=0.1
)

# --- PROMPTS ---

INTENT_SYSTEM_PROMPT = """You are the Intent & Action Compiler for a memory system.
Your ONLY job is to classify the user's message and extract structured data.
You do NOT generate a conversation. You output PURE JSON.

ACTIONS:
1. SAVE_MEMORY: User is explicitly sharing a fact, experience, feeling, or reflection to be remembered.
   - CRITICAL: Do NOT save questions. Do NOT save commands. Do NOT save greetings.
2. QUERY_MEMORY: User is asking a question about their past, patterns, or stored info.
3. OUT_OF_SCOPE: User is asking for general advice, opinions, hypotheticals, or chit-chat unrelated to memory.

OUTPUT FORMAT:
{
  "action": "SAVE_MEMORY" | "QUERY_MEMORY" | "OUT_OF_SCOPE",
  "memory_summary": "<literal_summary_if_save_else_null>",
  "entities": ["<entity1>", "<entity2>"],
  "tags": ["<tag1>", "<tag2>"]
}

RULES FOR SAVE_MEMORY:
- memory_summary MUST be a literal, third-person extraction of the user's statement.
- Do NOT infer emotions, stress, or meaning not present.
- Do NOT rewrite creatively. Keep it dry and factual.
- If the user asks a question, action MUST be QUERY_MEMORY (or OUT_OF_SCOPE).

RULES FOR QUERY_MEMORY / OUT_OF_SCOPE:
- memory_summary MUST be null.
- entities and tags can still be extracted if relevant to the query.
"""

RESPONSE_SYSTEM_PROMPT = """You are a Memory Response Generator.
Your task is to answer the user's query using ONLY the provided Retrieved Memories.

RULES:
- Use specific details from the context.
- Do NOT make things up (Hallucination).
- Do NOT give advice or act as a therapist.
- If the answer is not in the memories, state that the memory is insufficient or still forming.
- Be neutral, objective, and supportive but professional.
"""

# --- CORE LOGIC ---

async def classify_intent(message: str) -> Dict[str, Any]:
    """
    LLM Call #1: Determine intent and extract data.
    """
    prompt = f"""
{INTENT_SYSTEM_PROMPT}

User Message:
"{message}"

JSON Output:
"""
    try:
        response = llm_compiler.invoke(prompt)
        content = response.content.strip()
        
        # Parse JSON
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].strip()
            
        data = json.loads(content)
        
        # Validation
        if data.get("action") not in ["SAVE_MEMORY", "QUERY_MEMORY", "OUT_OF_SCOPE"]:
            return {"action": "OUT_OF_SCOPE", "memory_summary": None, "entities": [], "tags": []}

        return data
    except Exception as e:
        print(f"Intent Classification Failed: {e}")
        return {"action": "OUT_OF_SCOPE", "memory_summary": None, "entities": [], "tags": []}

async def handle_save_memory(db: Session, user: User, data: Dict[str, Any], original_text: str) -> str:
    """
    Execute storage logic for SAVE_MEMORY intent.
    """
    summary = data.get("memory_summary")
    entities = data.get("entities", [])
    tags = data.get("tags", [])
    
    if not summary:
        return "I couldn't process that memory. Please try again."

    # 1. Duplicate Detection (Idempotency)
    summary_vector = embeddings_model.embed_query(summary)
    
    # Check SemanticMemory for similarity
    existing = db.query(SemanticMemory).filter(
        SemanticMemory.user_id == user.id,
        SemanticMemory.embedding.l2_distance(summary_vector) < 0.15 # Strict threshold for "same conceptual memory"
    ).first()
    
    if existing:
        return "I already have a memory very similar to this."

    # 2. Create Raw Archive (Layer 4)
    memory_metadata = MemoryCreate(
        title="Chat Entry",
        description=summary,
        media_type=MediaType.TEXT,
        topic=tags[0] if tags else "General",
        mood=3, # Neutral
        people=entities,
        memory_date=datetime.now()
    )
    
    # Use MemoryService to create the record
    memory = await MemoryService.create_text_memory(db, user, original_text, memory_metadata)
    
    # Create Raw Chunks for Layer 4 immediately
    text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=200)
    chunks = text_splitter.split_text(original_text)
    if chunks:
        add_memory_chunks(db, user.id, memory.id, chunks)

    # 3. Create Semantic Memory (Layer 2)
    sem_mem = SemanticMemory(
        user_id=user.id,
        memory_id=memory.id,
        content=summary,
        emotion_weight=3,
        keywords=tags,
        embedding=summary_vector
    )
    db.add(sem_mem)
    
    # 4. Update Entity Memories (Layer 3)
    for ent_name in entities:
        entity = db.query(EntityMemory).filter(
            EntityMemory.user_id == user.id,
            EntityMemory.name == ent_name
        ).first()
        
        if entity:
            entity.observation_count += 1
            entity.last_interaction = func.now()
        else:
            entity = EntityMemory(
                user_id=user.id,
                name=ent_name,
                entity_type="Person", # Default
                summary=f"Mentioned in context of {tags}",
                last_interaction=func.now()
            )
            db.add(entity)
            
    db.commit()
    
    return "Memory saved."

async def handle_query_memory(db: Session, user: User, query: str) -> str:
    """
    Execute retrieval and generation for QUERY_MEMORY intent.
    """
    # 1. Embed Query
    query_vector = embeddings_model.embed_query(query)
    
    # 2. Layer 2 Retrieval (Semantic)
    semantic_memories = db.query(SemanticMemory).filter(
        SemanticMemory.user_id == user.id
    ).order_by(
        SemanticMemory.embedding.l2_distance(query_vector)
    ).limit(5).all()
    
    # 3. Layer 3 Retrieval (Entity)
    # Simple recent entities for now, or filtered by query entities if we extracted them
    # For now, get just global recent context
    entities = db.query(EntityMemory).filter(
        EntityMemory.user_id == user.id
    ).order_by(desc(EntityMemory.last_interaction)).limit(5).all()
    
    # 4. Construct Context
    context_str = "SEMANTIC MEMORIES:\n"
    if semantic_memories:
        context_str += "\n".join([f"- {m.content}" for m in semantic_memories])
    else:
        context_str += "None found."
        
    context_str += "\n\nENTITY CONTEXT:\n"
    if entities:
        context_str += "\n".join([f"- {e.name} ({e.observation_count} obs)" for e in entities])
    else:
        context_str += "None found."

    # 5. LLM Call #2: Generate Response
    prompt = f"""
{RESPONSE_SYSTEM_PROMPT}

RETRIEVED MEMORIES:
{context_str}

USER QUERY:
{query}
"""
    try:
        response = llm_responder.invoke(prompt)
        return response.content.strip()
    except Exception as e:
        return "I'm having trouble retrieving memories right now."

async def ask(db: Session, user: User, query: str, k=5) -> Dict[str, str]:
    """
    Main specific entry point.
    """
    # Step 1: Intent & Action Compiler
    intent_data = await classify_intent(query)
    
    action = intent_data.get("action")
    print(f"INTENT: {action}")
    
    if action == "SAVE_MEMORY":
        message = await handle_save_memory(db, user, intent_data, query)
        return {"answer": message}
        
    elif action == "QUERY_MEMORY":
        message = await handle_query_memory(db, user, query)
        return {"answer": message}
        
    else: # OUT_OF_SCOPE
        return {"answer": "I focus only on your memories. Please add a memory or ask about what's stored."}