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
- YOU MUST EXTRACT ALL NUMBERS, CODES, DATES, AND PROPER NOUNS EXACTLY.
- Example: "Code is 1234" -> "User states the code is 1234".
- Do NOT psychoanalyze or infer feelings ("User feels burdened"). Just state the fact.
- Do NOT rewrite creatively. Keep it dry and factual.
- If the user asks a question, action MUST be QUERY_MEMORY (or OUT_OF_SCOPE).

DURABILITY CHECK (CRITICAL):
- Only save memories that will be valid in 30 days.
- REJECT ephemeral states: "I'm hungry", "It's raining", "I'm tired today". (Mark as OUT_OF_SCOPE).
- ACCEPT durable facts: "I started a keto diet", "I moved to Seattle", "I broke my leg".

RULES FOR QUERY_MEMORY:
- User is asking for information that might be stored (past events, facts, preferences, codes, location, etc.).
- memory_summary MUST be null.
- entities and tags can still be extracted.

RULES FOR OUT_OF_SCOPE:
- User is asking for general knowledge (math, weather, history) NOT related to them.
- User is engaging in small talk ("hi", "how are you").
- memory_summary MUST be null.

CASUAL CONVERSATION (CRITICAL):
- If the user says "hi", "thanks", "ok", "cool", "nevermind":
- Action MUST be OUT_OF_SCOPE.
- Why? These are not memories. They are chat.
"""

RESPONSE_SYSTEM_PROMPT = """You are a Memory Response Generator.
Your task is to answer the user's query using ONLY the provided Retrieved Memories.

RULES:
- Use specific details from the context.
- Do NOT make things up (Hallucination).
- Do NOT give advice or act as a therapist.
- Be neutral, objective, and supportive but professional.
- BE NATURAL: Start with "I recall..." or "You mentioned...". Do NOT say "Based on retrieved memory".
- BE HUMAN: If the user says "hi", just say "Hi! What's on your mind?". Do not mention memory at all.
- BE COOPERATIVE: Acknowledgements ("ok", "cool") should be met with brief confirmations ("Ready whenever you are.").


"""

CONVERSATION_SHAPER_PROMPT = """You are a conversational response shaper.
Your job is NOT to store memory and NOT to retrieve memory.
Your job is ONLY to phrase the response in a natural, human way.

You are given:
- the user's message
- the system's intent decision
- what information is known
- what information is missing

RULES:
- Be friendly, calm, and human.
- Never explain system rules unless asked.
- Never sound like a database or error message.
- Never invent facts.
- If something is unknown, say so gently.
- If the user is casual (hi, ok, mmhmm), respond casually.
- If the user is emotional, acknowledge without diagnosing.
- If the system cannot do something, explain simply and redirect.

IMPORTANT:
You are allowed to infer *tone*, but NOT facts.
You are allowed to infer *intent*, but NOT memory.

Your response should sound like a helpful person, not a system.
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
    # A. Special handling for SELF entity if distinct from others
    # We always update USER_SELF to accumulate a running biography? 
    # Or strict prompt ensures 'summary' is specific.
    # Let's perform standard entity update.

    for ent_name in entities:
        # Check if ent_name is referring to self?
        target_name = ent_name
        if target_name.lower() in ["me", "i", "myself", "user"]:
             target_name = "USER_SELF"

        entity = db.query(EntityMemory).filter(
            EntityMemory.user_id == user.id,
            EntityMemory.name == target_name
        ).first()
        
        if entity:
            entity.observation_count += 1
            entity.last_interaction = func.now()
            # Ideally we would append to summary or refine it.
            # But that requires another LLM call. For now, we just track frequency.
        else:
            entity = EntityMemory(
                user_id=user.id,
                name=target_name,
                entity_type="Person", # Default
                summary=f"First mentioned in context of {tags}",
                last_interaction=func.now()
            )
            db.add(entity)
            
    db.commit()
    
    return "Got it — I've saved that for you."

async def handle_query_memory(db: Session, user: User, query: str) -> str:
    """
    Execute retrieval and generation for QUERY_MEMORY intent.
    """
    # 1. Identity Override Check (Fix 1: Hard-route Identity)
    q_lower = query.lower()
    identity_triggers = ["who am i", "what is my name", "my identity", "my role", "my occupation"]
    is_identity_query = any(trigger in q_lower for trigger in identity_triggers)

    # 2. Layer 3 Retrieval (Entity)
    # A. IDENTITY AUTHORITY (USER_SELF)
    user_identity = db.query(EntityMemory).filter(
        EntityMemory.user_id == user.id,
        EntityMemory.name == "USER_SELF"
    ).first()
    
    # If explicitly asking for name/identity, we MUST prioritize Authority.
    # We can even skip vector search if we have a solid answer to avoid contamination.
    if is_identity_query:
        # Check structured user fields first (if added to schema, currently using User model props if any)
        # Assuming User model might have 'full_name' or similar, but for now we rely on USER_SELF entity.
        if user_identity and user_identity.summary:
             # Fast track return or strongly weighted context
             pass # Will fall through to context construction, but key is we HAVE it.
        else:
             # If strictly asking "what is my name" and we don't have it -> Prompt intake.
             if "name" in q_lower:
                 return "I don't have your name stored yet. Would you like to add it?"

    # 3. Embed Query
    query_vector = embeddings_model.embed_query(query)
    
    # 4. Layer 2 Retrieval (Semantic)
    # Only if NOT identity query, OR if identity is partial? 
    # Actually, let's include semantic but warn about overriding.
    # Better: If identity query, we might want to restrict semantic search scope or filter.
    # But for now, standard retrieval is fine AS LONG AS prompt respects Authority Layer.
    
    semantic_memories = db.query(SemanticMemory).filter(
        SemanticMemory.user_id == user.id
    ).order_by(
        SemanticMemory.embedding.l2_distance(query_vector)
    ).limit(5).all()
    
    # B. General Entity Retrieval
    entities = db.query(EntityMemory).filter(
        EntityMemory.user_id == user.id,
        EntityMemory.name != "USER_SELF" 
    ).order_by(desc(EntityMemory.last_interaction)).limit(5).all()
    
    # 5. Construct Context
    context_str = "IDENTITY (Authority Layer - HIGHEST PRIORITY):\n"
    if user_identity and user_identity.summary:
        context_str += f"- {user_identity.summary}\n"
    elif user.name: # Fallback to User table if available.
        context_str += f"- Name: {user.name}\n"
    else:
        context_str += "No structured identity established.\n"

    context_str += "\nSEMANTIC MEMORIES (Layer 2):\n"
    if semantic_memories:
        context_str += "\n".join([f"- {m.content}" for m in semantic_memories])
    else:
        context_str += "None found."
        
    context_str += "\n\nENTITY CONTEXT (Layer 3):\n"
    if entities:
        context_str += "\n".join([f"- {e.name} ({e.observation_count} obs)" for e in entities])
    else:
        context_str += "None found."

    # 6. LLM Call #2: Generate Response
    prompt = f"""
{RESPONSE_SYSTEM_PROMPT}

CRITICAL IDENTITY RULE:
- NEVER define the user by similarity to another person.
- NEVER say "You are like Sanjeev" or "You share interests with Alex".
- Always answer "who am I" using FIRST-PERSON identity facts only.
- If identity is missing, ask for it.

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

async def handle_meta_query(db: Session, user: User, query: str) -> str:
    """
    Handle valid system/meta queries like 'summarize', 'list tags', 'json'.
    Bypass semantic search for these.
    """
    query_lower = query.lower()
    
    if "tag" in query_lower:
        # Fetch tags
        tags = [t[0] for t in db.query(SemanticMemory.keywords).filter(SemanticMemory.user_id == user.id).all()]
        # Flatten list of lists
        flat_tags = set([item for sublist in tags if sublist for item in sublist])
        return f"Here are the tags I have stored for you: {', '.join(flat_tags)}"
        
    if "summarize" in query_lower or "list" in query_lower or "last" in query_lower:
        # Fetch recent 5 memories
        mems = db.query(SemanticMemory).order_by(desc(SemanticMemory.created_at)).limit(5).all()
        if not mems:
             return "I don't have enough memories to summarize yet."
        summary = "\n".join([f"- {m.content}" for m in mems])
        return f"Here are your most recent memories:\n{summary}"

    return "I couldn't process that specific meta-request."

async def ask(db: Session, user: User, query: str, k=5) -> Dict[str, str]:
    """
    Main specific entry point.
    """
    # 0. Pre-check for meta-queries (Simple heuristics before expensive LLM)
    q_lower = query.lower()
    if any(x in q_lower for x in ["summarize", "list tags", "show tags", "json output", "last memory"]):
        # Route to logic handler
        ans = await handle_meta_query(db, user, query)
        return {"answer": ans}

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
        
    else: # OUT_OF_SCOPE / Conversation Layer
        # LLM Call #3: Conversation Shaper
        # Instead of hard rules, we ask the Shaper.
        
        prompt = f"""{CONVERSATION_SHAPER_PROMPT}

USER MESSAGE: "{query}"

SYSTEM INTENT: OUT_OF_SCOPE (User is chatting, asking unrelated questions, or being casual).

TASK: Respond naturally.
"""
        try:
             response = llm_responder.invoke(prompt) 
             content = response.content.strip()
             return {"answer": content}
        except Exception as e:
             print(f"Shaper Error: {e}")
             return {"answer": "I don't have a record of that yet. To help me learn, you can upload a memory, tell me about your day, or share a new fact!"}