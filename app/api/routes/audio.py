from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from datetime import datetime, timezone
from uuid import UUID
from typing import Optional

from app.api.deps import get_current_user
from app.schemas.audio import AudioProcessRequest, UploadRequest
from app.core.database import get_db
from app.models.user import User
from app.models.document import Document
from app.models.chunk import Chunk

from app.services.storage import (
    generate_signed_get_url, 
    generate_signed_upload_url, 
    download_json_from_storage,
    delete_from_storage
)
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

    filename = req.audio_key.split("/")[-1]
    
    # Save transcription to object storage using utility function
    from app.services.transcription_utils import save_transcription
    
    try:
        transcript_key = save_transcription(req.audio_key, transcript)
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to save transcription: {str(e)}")

    # Insert into Postgres via add_chunks
    doc_id = add_chunks(
        db=db,
        user=user,
        chunks=chunks,
        source=req.audio_key,
        filename=filename,
        transcript_key=transcript_key
    )

    return {
        "status": "indexed",
        "chunks": len(chunks),
        "document_id": str(doc_id),
        "filename": filename,
        "transcript_key": transcript_key
    }

@router.get("/audio/{document_id}")
def get_audio_with_transcription(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get audio file URL and transcription together for a specific document
    """
    # Fetch document and verify ownership
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user.id
        )
        .first()
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Generate signed URL for audio file
    audio_url = generate_signed_get_url(doc.source_key, expires_in=3600)
    
    # Get transcription if available
    transcription = None
    if doc.transcript_key:
        try:
            transcription = download_json_from_storage(doc.transcript_key)
        except Exception as e:
            # Don't fail if transcription is missing, just return None
            print(f"Warning: Failed to retrieve transcription: {str(e)}")
    
    return {
        "document_id": str(doc.id),
        "filename": doc.filename,
        "status": doc.status,
        "created_at": doc.created_at.isoformat(),
        "audio": {
            "url": audio_url,
            "key": doc.source_key,
            "expires_in": 3600
        },
        "transcription": transcription,
        "has_transcription": transcription is not None
    }

@router.get("/audio")
def list_audio_files(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
    page: int = Query(1, ge=1, description="Page number (starts at 1)"),
    page_size: int = Query(10, ge=1, le=100, description="Items per page (max 100)")
):
    """
    List all audio files with pagination
    """
    # Calculate offset
    offset = (page - 1) * page_size
    
    # Get total count
    total = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .count()
    )
    
    # Get paginated documents
    documents = (
        db.query(Document)
        .filter(Document.user_id == user.id)
        .order_by(Document.created_at.desc())
        .offset(offset)
        .limit(page_size)
        .all()
    )
    
    # Calculate pagination metadata
    total_pages = (total + page_size - 1) // page_size  # Ceiling division
    has_next = page < total_pages
    has_prev = page > 1
    
    # Format response
    items = []
    for doc in documents:
        items.append({
            "document_id": str(doc.id),
            "filename": doc.filename,
            "status": doc.status,
            "created_at": doc.created_at.isoformat(),
            "has_transcription": doc.transcript_key is not None,
            "audio_key": doc.source_key,
            "transcript_key": doc.transcript_key
        })
    
    return {
        "items": items,
        "pagination": {
            "page": page,
            "page_size": page_size,
            "total_items": total,
            "total_pages": total_pages,
            "has_next": has_next,
            "has_prev": has_prev
        }
    }

@router.delete("/audio/{document_id}")
def delete_audio(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete audio file, transcription, and all associated data
    """
    # Fetch document and verify ownership
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user.id
        )
        .first()
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    # Delete from S3
    audio_deleted = delete_from_storage(doc.source_key)
    transcript_deleted = False
    
    if doc.transcript_key:
        transcript_deleted = delete_from_storage(doc.transcript_key)
    
    # Delete chunks (will cascade delete due to foreign key)
    chunks_deleted = (
        db.query(Chunk)
        .filter(Chunk.document_id == document_id)
        .delete()
    )
    
    # Delete document
    db.delete(doc)
    db.commit()
    
    return {
        "status": "deleted",
        "document_id": str(document_id),
        "filename": doc.filename,
        "deleted": {
            "audio": audio_deleted,
            "transcription": transcript_deleted,
            "chunks": chunks_deleted,
            "database_record": True
        }
    }

@router.get("/transcription/{document_id}")
def get_transcription(
    document_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieve the transcription JSON for a specific document
    """
    # Fetch document and verify ownership
    doc = (
        db.query(Document)
        .filter(
            Document.id == document_id,
            Document.user_id == user.id
        )
        .first()
    )
    
    if not doc:
        raise HTTPException(status_code=404, detail="Document not found")
    
    if not doc.transcript_key:
        raise HTTPException(status_code=404, detail="No transcription available for this document")
    
    try:
        transcript_data = download_json_from_storage(doc.transcript_key)
        return {
            "document_id": str(doc.id),
            "filename": doc.filename,
            "transcript_key": doc.transcript_key,
            "transcription": transcript_data
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to retrieve transcription: {str(e)}")

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
