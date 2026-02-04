from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Form, BackgroundTasks, Query
from sqlalchemy.orm import Session
from typing import List, Optional
from uuid import UUID
import json

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.schemas.memory import (
    TagCreate, TagUpdate, TagResponse,
    MemoryCreate, MemoryUpdate, MemoryResponse, MemoryListResponse,
    MemoryFilterParams, MemoryUploadMetadata, MemoryURLResponse, MemoryTextResponse
)
from app.services.memory_service import TagService, MemoryService
from app.services.memory_processor import process_memory_background
from app.models.memory import MediaType, ProcessingStatus

router = APIRouter(prefix="/memories", tags=["memories"])


# ============ Tag Endpoints ============

@router.post("/tags", response_model=TagResponse, status_code=status.HTTP_201_CREATED)
def create_tag(
    tag_data: TagCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a new tag.
    
    Tags are used to categorize and organize memories.
    Each tag must have a unique name per user.
    """
    tag = TagService.create_tag(db, user, tag_data)
    tag.memory_count = 0
    return tag


@router.get("/tags", response_model=List[TagResponse])
def list_tags(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List all tags for the current user.
    
    Returns tags with their associated memory counts.
    """
    return TagService.list_tags(db, user)


@router.get("/tags/{tag_id}", response_model=TagResponse)
def get_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get a specific tag by ID."""
    tag = TagService.get_tag(db, user, tag_id)
    if not tag:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Tag not found"
        )
    return tag


@router.patch("/tags/{tag_id}", response_model=TagResponse)
def update_tag(
    tag_id: UUID,
    tag_data: TagUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update a tag.
    
    You can update the name and/or color of a tag.
    """
    return TagService.update_tag(db, user, tag_id, tag_data)


@router.delete("/tags/{tag_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_tag(
    tag_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete a tag.
    
    This will remove the tag from all memories but won't delete the memories themselves.
    """
    TagService.delete_tag(db, user, tag_id)
    return None


# ============ Memory Endpoints ============

@router.post("/upload", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def upload_memory(
    background_tasks: BackgroundTasks,
    file: UploadFile = File(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Upload a new memory (audio, video, or text file).
    
    **Supported file types:**
    - Audio: mp3, wav, m4a, etc.
    - Video: mp4, mov, avi, etc.
    - Text: txt, md, etc.
    
    **Processing pipeline:**
    1. File is uploaded to object storage
    2. For video: Audio is extracted using ffmpeg
    3. For audio/video: Transcription via AssemblyAI (with speaker diarization)
    4. Content is indexed in vector store for RAG queries
    
    **Metadata (optional JSON string):**
    ```json
    {
        "title": "My Memory",
        "description": "Description of the memory",
        "topic": "Work Meeting",
        "mood": 4,
        "people": ["John", "Sarah"],
        "tag_ids": ["uuid1", "uuid2"],
        "memory_date": "2026-02-03T10:00:00Z"
    }
    ```
    """
    # Parse metadata if provided
    memory_metadata = MemoryCreate()
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
            memory_metadata = MemoryCreate(**metadata_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid metadata JSON: {str(e)}"
            )
    
    # Create memory record
    memory = await MemoryService.create_memory_from_upload(db, user, file, memory_metadata)
    
    # Process in background
    background_tasks.add_task(process_memory_background, memory.id, db)
    
    return memory


@router.post("/text", response_model=MemoryResponse, status_code=status.HTTP_201_CREATED)
async def create_text_memory(
    background_tasks: BackgroundTasks,
    text_content: str = Form(...),
    metadata: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a memory from text content.
    
    This endpoint allows you to create a memory directly from text
    without uploading a file.
    """
    # Parse metadata
    memory_metadata = MemoryCreate()
    if metadata:
        try:
            metadata_dict = json.loads(metadata)
            memory_metadata = MemoryCreate(**metadata_dict)
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Invalid metadata JSON: {str(e)}"
            )
    
    # Create memory
    memory = await MemoryService.create_text_memory(db, user, text_content, memory_metadata)
    
    # Process in background
    background_tasks.add_task(process_memory_background, memory.id, db)
    
    return memory


@router.get("", response_model=MemoryListResponse)
def list_memories(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    media_type: Optional[MediaType] = None,
    topic: Optional[str] = None,
    mood: Optional[int] = Query(None, ge=1, le=5),
    status_filter: Optional[ProcessingStatus] = None,
    search: Optional[str] = None,
    tag_ids: Optional[str] = Query(None, description="Comma-separated tag IDs"),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List memories with pagination and filtering.
    
    **Filter options:**
    - `media_type`: Filter by audio, video, or text
    - `topic`: Search in topic field
    - `mood`: Filter by mood (1-5)
    - `status_filter`: Filter by processing status
    - `search`: Search in title, description, and topic
    - `tag_ids`: Filter by tag IDs (comma-separated UUIDs)
    
    **Example:**
    ```
    GET /memories?page=1&page_size=20&media_type=audio&mood=5&search=meeting
    ```
    """
    # Parse tag IDs if provided
    tag_id_list = None
    if tag_ids:
        try:
            tag_id_list = [UUID(tid.strip()) for tid in tag_ids.split(",")]
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid tag ID format"
            )
    
    # Build filter params
    filters = MemoryFilterParams(
        media_type=media_type,
        topic=topic,
        mood=mood,
        status=status_filter,
        search=search,
        tag_ids=tag_id_list
    )
    
    # Get memories
    memories, total = MemoryService.list_memories(db, user, page, page_size, filters)
    
    # Calculate total pages
    total_pages = (total + page_size - 1) // page_size
    
    return MemoryListResponse(
        items=memories,
        total=total,
        page=page,
        page_size=page_size,
        total_pages=total_pages
    )


@router.get("/{memory_id}", response_model=MemoryResponse)
def get_memory(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """Get a specific memory by ID."""
    memory = MemoryService.get_memory(db, user, memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    return memory


@router.patch("/{memory_id}", response_model=MemoryResponse)
def update_memory(
    memory_id: UUID,
    update_data: MemoryUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update a memory's metadata.
    
    You can update:
    - title, description
    - topic, mood, people
    - tags (by providing tag_ids)
    - memory_date
    """
    return MemoryService.update_memory(db, user, memory_id, update_data)


@router.delete("/{memory_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_memory(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete a memory.
    
    This will:
    - Delete the memory record from the database
    - Delete associated files from object storage (original file, audio, transcript)
    - Remove from vector store
    """
    await MemoryService.delete_memory(db, user, memory_id)
    return None


@router.get("/{memory_id}/audio-url", response_model=MemoryURLResponse)
async def get_memory_audio_url(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get the signed URL for the audio file.
    
    For video memories, this returns the extracted audio URL.
    For audio memories, this returns the source file URL.
    """
    memory = MemoryService.get_memory(db, user, memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    if memory.media_type == MediaType.TEXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Text memories do not have audio files"
        )
        
    # Determine which key to use
    key = None
    if memory.media_type == MediaType.AUDIO:
        key = memory.source_key
    elif memory.media_type == MediaType.VIDEO:
        if memory.audio_key:
            key = memory.audio_key
        else:
             # If audio key is missing for video, check status
             if memory.status in [ProcessingStatus.PENDING, ProcessingStatus.PROCESSING]:
                  raise HTTPException(
                      status_code=status.HTTP_404_NOT_FOUND, 
                      detail="Audio extraction in progress"
                  )
             raise HTTPException(
                 status_code=status.HTTP_404_NOT_FOUND, 
                 detail="Audio not available for this video"
             )
    
    if not key:
         raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="File not found")

    from app.services.storage import get_file_url
    url = await get_file_url(key)
    
    return MemoryURLResponse(url=url)


@router.get("/{memory_id}/video-url", response_model=MemoryURLResponse)
async def get_memory_video_url(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get the signed URL for the video file.
    Only available for video memories.
    """
    memory = MemoryService.get_memory(db, user, memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    if memory.media_type != MediaType.VIDEO:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This memory is not a video"
        )
        
    # Use source_key for video file
    from app.services.storage import get_file_url
    url = await get_file_url(memory.source_key)
    
    return MemoryURLResponse(url=url)


@router.get("/{memory_id}/text", response_model=MemoryTextResponse)
async def get_memory_text(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get the text content of a memory.
    Only available for text memories.
    """
    memory = MemoryService.get_memory(db, user, memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    if memory.media_type != MediaType.TEXT:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This memory is not a text memory"
        )
        
    from app.services.storage import download_text_from_storage
    try:
        content = download_text_from_storage(memory.source_key)
        return MemoryTextResponse(content=content)
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to retrieve text content: {str(e)}"
        )


@router.get("/{memory_id}/transcript")
async def get_memory_transcript(
    memory_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get the transcript for a memory.
    
    Returns the full transcript JSON including speaker diarization
    if the memory is audio or video.
    """
    memory = MemoryService.get_memory(db, user, memory_id)
    if not memory:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Memory not found"
        )
    
    if not memory.transcript_key:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transcript not available yet"
        )
    
    # Get transcript from storage
    from app.services.storage import get_file_url
    import requests
    
    transcript_url = await get_file_url(memory.transcript_key)
    response = requests.get(transcript_url)
    
    return response.json()
