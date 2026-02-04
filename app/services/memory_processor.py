import asyncio
import subprocess
import tempfile
import os
import json
from uuid import UUID
from typing import List
from sqlalchemy.orm import Session
from fastapi import UploadFile

from app.core.database import get_db
from app.models.memory import Memory, MediaType, ProcessingStatus
from app.services.storage import get_file_url, upload_file
from app.services.transcription import transcribe_from_url
from app.services.vectorstore import add_memory_chunks
from app.services.memory_service import MemoryService
from app.services.chunking import chunk_transcript

# Import text splitter for text memories
from langchain_text_splitters import RecursiveCharacterTextSplitter


async def process_memory_background(memory_id: UUID, db: Session):
    """
    Background task to process a memory:
    1. For VIDEO: Extract audio using ffmpeg
    2. For AUDIO/VIDEO: Transcribe using AssemblyAI
    3. For all types: Chunk and add to vector store for RAG
    """
    try:
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if not memory:
            print(f"Memory {memory_id} not found")
            return
        
        # Update status to processing
        MemoryService.update_processing_status(
            db, memory_id, ProcessingStatus.PROCESSING
        )
        
        chunks_to_index = []
        
        # Step 1: Handle video files - extract audio
        if memory.media_type == MediaType.VIDEO:
            try:
                audio_key = await extract_audio_from_video(memory.source_key, db)
                memory.audio_key = audio_key
                db.commit()
            except Exception as e:
                raise Exception(f"Failed to extract audio from video: {str(e)}")
        
        # Step 2: Transcribe audio/video
        if memory.media_type in [MediaType.AUDIO, MediaType.VIDEO]:
            try:
                # Get audio URL
                audio_key = memory.audio_key if memory.media_type == MediaType.VIDEO else memory.source_key
                audio_url = await get_file_url(audio_key)
                
                # Transcribe
                transcript = transcribe_from_url(audio_url)
                
                # Upload transcript JSON
                from io import BytesIO
                transcript_bytes = json.dumps(transcript).encode('utf-8')
                transcript_file = UploadFile(
                    filename=f"transcript_{memory_id}.json",
                    file=BytesIO(transcript_bytes),
                    headers={"content-type": "application/json"}
                )
                
                transcript_key = await upload_file(transcript_file)
                memory.transcript_key = transcript_key
                db.commit()
                
                # Chunk the transcript using existing chunking service
                # chunk_transcript returns list of dicts: {'text': '...', 'start': ..., 'end': ...}
                transcript_chunks = chunk_transcript(transcript)
                chunks_to_index = [c["text"] for c in transcript_chunks]
                
            except Exception as e:
                raise Exception(f"Failed to transcribe: {str(e)}")
        
        # Step 3: Handle text files
        elif memory.media_type == MediaType.TEXT:
            try:
                # Download text content
                text_url = await get_file_url(memory.source_key)
                import requests
                response = requests.get(text_url)
                response.encoding = 'utf-8' # Ensure utf-8
                text_content = response.text
                
                # Chunk text using LangChain
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=1000,
                    chunk_overlap=200,
                    length_function=len,
                )
                chunks_to_index = text_splitter.split_text(text_content)
                
            except Exception as e:
                raise Exception(f"Failed to process text file: {str(e)}")
        
        # Step 4: Add to vector store for RAG
        try:
            if chunks_to_index:
                add_memory_chunks(
                    db=db,
                    user_id=memory.user_id,
                    memory_id=memory.id,
                    text_chunks=chunks_to_index
                )
        except Exception as e:
            raise Exception(f"Failed to add to vector store: {str(e)}")
        
        # Update status to completed
        MemoryService.update_processing_status(
            db, memory_id, ProcessingStatus.COMPLETED
        )
        
    except Exception as e:
        print(f"Error processing memory {memory_id}: {str(e)}")
        # Re-query memory to ensure we have attached session if needed, though db session should persist
        MemoryService.update_processing_status(
            db, memory_id, ProcessingStatus.FAILED, str(e)
        )


async def extract_audio_from_video(video_key: str, db: Session) -> str:
    """
    Extract audio from video file using ffmpeg
    Returns the S3 key of the extracted audio file
    """
    # Get video URL
    video_url = await get_file_url(video_key)
    
    # Download video to temp file
    import requests
    with tempfile.NamedTemporaryFile(suffix='.mp4', delete=False) as video_temp:
        response = requests.get(video_url, stream=True)
        for chunk in response.iter_content(chunk_size=8192):
            video_temp.write(chunk)
        video_temp_path = video_temp.name
    
    audio_temp_path = None
    try:
        # Create temp file path for audio
        audio_temp_path = tempfile.mktemp(suffix='.mp3')
        
        # Extract audio using ffmpeg
        command = [
            'ffmpeg',
            '-i', video_temp_path,
            '-vn',  # No video
            '-acodec', 'libmp3lame',  # MP3 codec
            '-ar', '44100',  # Sample rate
            '-ac', '2',  # Stereo
            '-b:a', '192k',  # Bitrate
            '-y',  # Overwrite output file
            audio_temp_path
        ]
        
        # Run ffmpeg
        result = subprocess.run(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            timeout=300  # 5 minutes timeout
        )
        
        if result.returncode != 0:
            raise Exception(f"ffmpeg error: {result.stderr.decode()}")
        
        # Upload extracted audio
        if not os.path.exists(audio_temp_path) or os.path.getsize(audio_temp_path) == 0:
             raise Exception("Extracted audio file is empty or missing")

        with open(audio_temp_path, 'rb') as audio_file:
            audio_upload = UploadFile(
                filename=f"extracted_audio_{video_key.split('/')[-1]}.mp3",
                file=audio_file,
                headers={"content-type": "audio/mpeg"}
            )
            audio_key = await upload_file(audio_upload)
        
        return audio_key
        
    finally:
        # Cleanup temp files
        if os.path.exists(video_temp_path):
            os.remove(video_temp_path)
        if audio_temp_path and os.path.exists(audio_temp_path):
            os.remove(audio_temp_path)
