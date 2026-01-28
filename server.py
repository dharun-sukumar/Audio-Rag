from fastapi import FastAPI
from pydantic import BaseModel
from transcription import transcribe_from_url
from chunking import chunk_transcript
from vectorstore import add_chunks
from rag import ask
from datetime import datetime, timezone
from storage import generate_signed_get_url

app = FastAPI()

class AudioProcessRequest(BaseModel):
    audio_key: str  # e.g. audio/meeting.mp3

@app.post("/process-audio")
def process_audio(req: AudioProcessRequest):
    signed_url = generate_signed_get_url(req.audio_key)

    transcript = transcribe_from_url(signed_url)
    chunks = chunk_transcript(transcript)

    uploaded_at = datetime.now(timezone.utc)
    date_str = uploaded_at.date().isoformat()
    filename = req.audio_key.split("/")[-1]

    add_chunks(
        chunks=chunks,
        source=req.audio_key,
        filename=filename,
        uploaded_at=uploaded_at.isoformat(),
        date=date_str
    )

    return {
        "status": "indexed",
        "chunks": len(chunks),
        "date": date_str,
        "filename": filename
    }

@app.post("/ask")
def ask_question(q: dict):
    return ask(q["query"])
