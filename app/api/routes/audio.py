from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from datetime import datetime, timezone

from app.api.deps import get_current_user
from app.schemas.audio import AudioProcessRequest, UploadRequest
from app.core.database import get_db
from app.models.user import User

from app.services.storage import generate_signed_get_url, generate_signed_upload_url
from app.services.transcription import transcribe_from_url
from app.services.chunking import chunk_transcript
from app.services.vectorstore import add_chunks

router = APIRouter()

@router.post("/process-audio")
def process_audio(
    req: AudioProcessRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    signed_url = generate_signed_get_url(req.audio_key)

    try:
        transcript = transcribe_from_url(signed_url)
    except Exception as e:
         raise HTTPException(status_code=500, detail=f"Transcription failed: {str(e)}")
         
    chunks = chunk_transcript(transcript)

    if not chunks:
        return {
            "status": "error",
            "message": "No chunks generated from transcript",
            "transcript_words": len(transcript.get("words", [])),
        }

    uploaded_at = datetime.now(timezone.utc)
    # date_str = uploaded_at.date().isoformat()
    filename = req.audio_key.split("/")[-1]

    # Insert into Postgres via add_chunks
    doc_id = add_chunks(
        db=db,
        user=user,
        chunks=chunks,
        source=req.audio_key,
        filename=filename
    )

    return {
        "status": "indexed",
        "chunks": len(chunks),
        "document_id": str(doc_id),
        "filename": filename
    }

@router.post("/generate-upload-url")
def generate_upload_url(
    req: UploadRequest,
    user: User = Depends(get_current_user)
):
    """
    Generates a signed PUT URL for frontend direct upload
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%d_%H-%M-%S")
    safe_filename = req.filename.replace(" ", "_")
    object_key = f"audio/{timestamp}_{safe_filename}"

    upload_url = generate_signed_upload_url(
        key=object_key,
        content_type=req.mime,
        expires_in=300
    )

    return {
        "upload_url": upload_url,
        "object_key": object_key,
        "expires_in": 300
    }
