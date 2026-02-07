import json
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.models.memory import Memory, SemanticMemory, EntityMemory
from app.services.vectorstore import embeddings_model
from app.core.config import GROQ_API_KEY, LLM_MODEL
from groq import Groq
import os

client = Groq(api_key=GROQ_API_KEY)

PARTICIPANT_SYSTEM_PROMPT = """You are an internal memory-distillation system for a private digital diary.

Your job is to convert a user’s raw diary entry into a semantic memory snapshot that can be stored long-term and used later for personalized reflection.

Core Rules (do not break these)

Do NOT rewrite or summarize the diary text verbatim.
Do NOT include dates, exact quotes, or specific events unless emotionally meaningful.
Do NOT judge, advise, diagnose, or therapize.
Do NOT assume facts not present.
Preserve emotional nuance without exaggeration.
Write in third-person, neutral tone.

What to Extract
Focus only on information that would still matter weeks or months later:
- Emotional state: dominant emotions, emotional tension or conflict, emotional shift (if any)
- Patterns: repeated feelings, recurring situations, ongoing struggles or improvements
- People (if mentioned): emotional association with each person, nature of interactions
- Internal narratives: self-beliefs, doubts, motivations or fears

Output Format (strict)
Return a single short paragraph of 3–6 sentences.
No bullet points. No emojis. No advice. No questions.

Example Output:
“The user experienced emotional fatigue and frustration related to work. Interactions with Alex were associated with dismissal and diminished confidence. A recurring pattern of self-silencing appeared despite awareness of the issue. The day ended with self-directed disappointment rather than external blame.”
"""

def distill_memory(db: Session, memory_id: str):
    """
    Generate a semantic memory snapshot and extract entity insights.
    """
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        return

    # Check if snapshot already exists
    existing = db.query(SemanticMemory).filter(SemanticMemory.memory_id == memory_id).first()
    if existing:
        return

    # 1. Prepare Input for LLM
    # We need the actual text content.
    # If it's text, download it. If it's audio/video, get the transcript.
    # For now, let's assume we have access to the transcript content or text content via the previous step in processor
    # But since this is a separate service call, we might need to fetch it again or pass it in.
    # However, to keep it clean, let's fetch.
    
    content_text = ""
    if memory.media_type == "text":
        from app.services.storage import download_text_from_storage
        try:
            content_text = download_text_from_storage(memory.source_key)
        except:
            return # Can't process
    else:
        # Transcript
        if not memory.transcript_key:
            return 
        from app.services.storage import get_file_url
        import requests
        try:
            # We need the full transcript text, not just chunks
            # Usually transcript json has 'text' field?
            import asyncio
            # We are in a sync function here?
            # Creating a new event loop or using async_to_sync might be complex if called from async.
            # But wait, download_text_from_storage is sync.
            # get_file_url is async.
            # Let's assume we can get the text.
            # For this MVP, let's rely on the caller passing text or handle it better.
            pass
        except:
            return

    # Actually, the memory processor calls this. Let's make this accept text_content directly to avoid re-fetching.
    pass

def generate_semantic_snapshot(text_content: str, mood: int, tags: list, people: list) -> str:
    """
    Generate the snapshot using LLM.
    """
    
    # Construct prompt
    user_input = f"""
    Raw diary text: "{text_content}"
    Emotion score: {mood if mood else 'Not provided'}
    User-provided tags: {", ".join([t.name for t in tags]) if tags else 'None'}
    Mentioned people: {", ".join(people) if people else 'None'}
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": PARTICIPANT_SYSTEM_PROMPT},
                {"role": "user", "content": user_input}
            ],
            model=LLM_MODEL,
            temperature=0.1, # Low temp for consistent, grounded output
        )
        return completion.choices[0].message.content.strip()
    except Exception as e:
        print(f"LLM generation failed: {e}")
        return None

def extract_entities(text_content: str) -> list:
    """
    Extract entity observations.
    """
    # Simply ask LLM to identify people/entities and their context.
    # We can reuse the same call or make a new one. 
    # For efficiency, maybe do it in one go with structured output?
    # But user asked for specific "entity memories" layer.
    
    prompt = """
    Identify people mentioned in the text and summarize the user's interaction/feeling towards them in 1 sentence.
    Output JSON format: [{"name": "Name", "summary": "Interaction summary"}]
    """
    
    try:
        completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": prompt},
                {"role": "user", "content": text_content}
            ],
            model=LLM_MODEL,
            response_format={"type": "json_object"}
        )
        content = completion.choices[0].message.content
        try:
             # Depending on model, it might wrap in Markdown code blocks
             if "```json" in content:
                 content = content.split("```json")[1].split("```")[0].strip()
             elif "```" in content:
                 content = content.split("```")[1].strip()
             return json.loads(content)
        except:
             return []
    except:
        return []

async def process_semantic_memory(db: Session, memory_id: str, text_content: str):
    """
    Orchestrate the creation of semantic memory and entity updates.
    """
    memory = db.query(Memory).filter(Memory.id == memory_id).first()
    if not memory:
        return

    # 1. Generate Snapshot
    snapshot = generate_semantic_snapshot(text_content, memory.mood, memory.tags, memory.people)
    if not snapshot:
        return

    # 2. Create Semantic Memory Record
    # Generate embedding
    embedding = embeddings_model.embed_query(snapshot)
    
    sem_mem = SemanticMemory(
        user_id=memory.user_id,
        memory_id=memory.id,
        content=snapshot,
        emotion_weight=memory.mood,
        embedding=embedding
    )
    db.add(sem_mem)
    
    # 3. Entity Updates (Simplified for MVP)
    # We could parse people from metadata + text to find entities
    # For each person in memory.people:
    # Update or create EntityMemory
    if memory.people:
        for person_name in memory.people:
            # Find existing
            # Find existing
            # Note: tags/people strings might not match exactly. Just simple exact match for now.
            entity = db.query(EntityMemory).filter(
                EntityMemory.user_id == memory.user_id,
                EntityMemory.name == person_name
            ).first()
            
            if entity:
                entity.observation_count += 1
                entity.last_interaction = func.now()
                # Ideally we update summary too with new info
            else:
                entity = EntityMemory(
                    user_id=memory.user_id,
                    name=person_name,
                    entity_type="Person",
                    summary=f"First mentioned in memory {memory.title}",
                    last_interaction=func.now()
                )
                db.add(entity)
    
    db.commit()
