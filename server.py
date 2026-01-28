from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from transcription import transcribe_from_url
from chunking import chunk_transcript
from vectorstore import add_chunks
from rag import ask
from datetime import datetime, timezone
from storage import generate_signed_get_url, generate_signed_upload_url

app = FastAPI(
    servers=[
        {"url": "http://139.59.19.169", "description": "production"}
    ]
)

# Configure CORS to allow all origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allows all origins
    allow_credentials=True,
    allow_methods=["*"],  # Allows all methods
    allow_headers=["*"],  # Allows all headers
)

class AudioProcessRequest(BaseModel):
    audio_key: str  # e.g. audio/meeting.mp3

class UploadRequest(BaseModel):
    filename: str
    mime: str

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

@app.post("/generate-upload-url")
def generate_upload_url(req: UploadRequest):
    """
    Generates a signed PUT URL for frontend direct upload
    """

    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    safe_filename = req.filename.replace(" ", "_")

    object_key = f"audio/{timestamp}_{safe_filename}"

    upload_url = generate_signed_upload_url(
        key=object_key,
        content_type=req.mime,
        expires_in=300  # 5 minutes
    )

    return {
        "upload_url": upload_url,
        "object_key": object_key,
        "expires_in": 300
    }
