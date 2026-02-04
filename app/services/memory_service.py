import os
import uuid
import mimetypes
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from sqlalchemy import or_, and_, func
from datetime import datetime
from fastapi import UploadFile, HTTPException, status

from app.models.memory import Memory, Tag, MediaType, ProcessingStatus
from app.models.user import User
from app.schemas.memory import (
    MemoryCreate, MemoryUpdate, MemoryFilterParams,
    TagCreate, TagUpdate
)
from app.services.storage import upload_file, delete_file
from app.services.transcription import transcribe_from_url


class TagService:
    """Service for managing tags"""
    
    @staticmethod
    def create_tag(db: Session, user: User, tag_data: TagCreate) -> Tag:
        """Create a new tag"""
        # Check if tag with same name already exists for this user
        existing = db.query(Tag).filter(
            and_(
                Tag.user_id == user.id,
                Tag.name == tag_data.name
            )
        ).first()
        
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Tag with name '{tag_data.name}' already exists"
            )
        
        tag = Tag(
            user_id=user.id,
            name=tag_data.name,
            color=tag_data.color
        )
        db.add(tag)
        db.commit()
        db.refresh(tag)
        return tag
    
    @staticmethod
    def get_tag(db: Session, user: User, tag_id: uuid.UUID) -> Optional[Tag]:
        """Get a tag by ID"""
        return db.query(Tag).filter(
            and_(Tag.id == tag_id, Tag.user_id == user.id)
        ).first()
    
    @staticmethod
    def list_tags(db: Session, user: User) -> List[Tag]:
        """List all tags for a user with memory counts"""
        tags = db.query(
            Tag,
            func.count(Memory.id).label('memory_count')
        ).outerjoin(
            Memory.tags
        ).filter(
            Tag.user_id == user.id
        ).group_by(Tag.id).all()
        
        # Attach memory count to each tag
        result = []
        for tag, count in tags:
            tag.memory_count = count
            result.append(tag)
        
        return result
    
    @staticmethod
    def update_tag(db: Session, user: User, tag_id: uuid.UUID, tag_data: TagUpdate) -> Tag:
        """Update a tag"""
        tag = TagService.get_tag(db, user, tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found"
            )
        
        if tag_data.name is not None:
            # Check for name conflict
            existing = db.query(Tag).filter(
                and_(
                    Tag.user_id == user.id,
                    Tag.name == tag_data.name,
                    Tag.id != tag_id
                )
            ).first()
            if existing:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Tag with name '{tag_data.name}' already exists"
                )
            tag.name = tag_data.name
        
        if tag_data.color is not None:
            tag.color = tag_data.color
        
        db.commit()
        db.refresh(tag)
        return tag
    
    @staticmethod
    def delete_tag(db: Session, user: User, tag_id: uuid.UUID) -> bool:
        """Delete a tag"""
        tag = TagService.get_tag(db, user, tag_id)
        if not tag:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Tag not found"
            )
        
        db.delete(tag)
        db.commit()
        return True


class MemoryService:
    """Service for managing memories"""
    
    @staticmethod
    def detect_media_type(file: UploadFile) -> MediaType:
        """Detect media type from file"""
        content_type = file.content_type or mimetypes.guess_type(file.filename)[0] or ""
        
        if content_type.startswith("audio/"):
            return MediaType.AUDIO
        elif content_type.startswith("video/"):
            return MediaType.VIDEO
        elif content_type.startswith("text/"):
            return MediaType.TEXT
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Unsupported file type: {content_type}"
            )
    
    @staticmethod
    async def create_memory_from_upload(
        db: Session,
        user: User,
        file: UploadFile,
        metadata: MemoryCreate
    ) -> Memory:
        """Create a memory from uploaded file"""
        # Detect media type
        media_type = MemoryService.detect_media_type(file)
        
        # Upload original file to object storage
        source_key = await upload_file(file)
        
        # Create memory record
        memory = Memory(
            user_id=user.id,
            title=metadata.title or file.filename,
            description=metadata.description,
            media_type=media_type,
            source_key=source_key,
            topic=metadata.topic,
            mood=metadata.mood,
            people=metadata.people or [],
            memory_date=metadata.memory_date,
            status=ProcessingStatus.PENDING
        )
        
        # Add tags if provided
        if metadata.tag_ids:
            tags = db.query(Tag).filter(
                and_(
                    Tag.id.in_(metadata.tag_ids),
                    Tag.user_id == user.id
                )
            ).all()
            memory.tags = tags
        
        db.add(memory)
        db.commit()
        db.refresh(memory)
        
        return memory
    
    @staticmethod
    async def create_text_memory(
        db: Session,
        user: User,
        text_content: str,
        metadata: MemoryCreate
    ) -> Memory:
        """Create a memory from text content"""
        # Create a temporary file-like object for text
        from io import BytesIO
        from fastapi import UploadFile as FastAPIUploadFile
        
        text_bytes = text_content.encode('utf-8')
        text_file = FastAPIUploadFile(
            filename=f"text_memory_{uuid.uuid4()}.txt",
            file=BytesIO(text_bytes),
            headers={"content-type": "text/plain"}
        )
        
        # Upload to storage
        source_key = await upload_file(text_file)
        
        # Create memory record
        memory = Memory(
            user_id=user.id,
            title=metadata.title or "Text Memory",
            description=metadata.description,
            media_type=MediaType.TEXT,
            source_key=source_key,
            topic=metadata.topic,
            mood=metadata.mood,
            people=metadata.people or [],
            memory_date=metadata.memory_date,
            status=ProcessingStatus.PENDING
        )
        
        # Add tags
        if metadata.tag_ids:
            tags = db.query(Tag).filter(
                and_(
                    Tag.id.in_(metadata.tag_ids),
                    Tag.user_id == user.id
                )
            ).all()
            memory.tags = tags
        
        db.add(memory)
        db.commit()
        db.refresh(memory)
        
        return memory
    
    @staticmethod
    def get_memory(db: Session, user: User, memory_id: uuid.UUID) -> Optional[Memory]:
        """Get a memory by ID"""
        return db.query(Memory).filter(
            and_(Memory.id == memory_id, Memory.user_id == user.id)
        ).first()
    
    @staticmethod
    def list_memories(
        db: Session,
        user: User,
        page: int = 1,
        page_size: int = 20,
        filters: Optional[MemoryFilterParams] = None
    ) -> Tuple[List[Memory], int]:
        """List memories with pagination and filters"""
        query = db.query(Memory).filter(Memory.user_id == user.id)
        
        # Apply filters
        if filters:
            if filters.media_type:
                query = query.filter(Memory.media_type == filters.media_type)
            
            if filters.topic:
                query = query.filter(Memory.topic.ilike(f"%{filters.topic}%"))
            
            if filters.mood:
                query = query.filter(Memory.mood == filters.mood)
            
            if filters.status:
                query = query.filter(Memory.status == filters.status)
            
            if filters.tag_ids:
                query = query.join(Memory.tags).filter(Tag.id.in_(filters.tag_ids))
            
            if filters.search:
                search_term = f"%{filters.search}%"
                query = query.filter(
                    or_(
                        Memory.title.ilike(search_term),
                        Memory.description.ilike(search_term),
                        Memory.topic.ilike(search_term)
                    )
                )
            
            if filters.start_date:
                query = query.filter(Memory.created_at >= filters.start_date)
            
            if filters.end_date:
                query = query.filter(Memory.created_at <= filters.end_date)
        
        # Get total count
        total = query.count()
        
        # Apply pagination
        offset = (page - 1) * page_size
        memories = query.order_by(Memory.created_at.desc()).offset(offset).limit(page_size).all()
        
        return memories, total
    
    @staticmethod
    def update_memory(
        db: Session,
        user: User,
        memory_id: uuid.UUID,
        update_data: MemoryUpdate
    ) -> Memory:
        """Update a memory"""
        memory = MemoryService.get_memory(db, user, memory_id)
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        # Update fields
        if update_data.title is not None:
            memory.title = update_data.title
        
        if update_data.description is not None:
            memory.description = update_data.description
        
        if update_data.topic is not None:
            memory.topic = update_data.topic
        
        if update_data.mood is not None:
            memory.mood = update_data.mood
        
        if update_data.people is not None:
            memory.people = update_data.people
        
        if update_data.memory_date is not None:
            memory.memory_date = update_data.memory_date
        
        # Update tags
        if update_data.tag_ids is not None:
            tags = db.query(Tag).filter(
                and_(
                    Tag.id.in_(update_data.tag_ids),
                    Tag.user_id == user.id
                )
            ).all()
            memory.tags = tags
        
        db.commit()
        db.refresh(memory)
        return memory
    
    @staticmethod
    async def delete_memory(db: Session, user: User, memory_id: uuid.UUID) -> bool:
        """Delete a memory and associated files"""
        memory = MemoryService.get_memory(db, user, memory_id)
        if not memory:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Memory not found"
            )
        
        # Delete files from storage
        try:
            await delete_file(memory.source_key)
            if memory.audio_key:
                await delete_file(memory.audio_key)
            if memory.transcript_key:
                await delete_file(memory.transcript_key)
        except Exception as e:
            print(f"Error deleting files: {e}")
            # Continue with database deletion even if file deletion fails
        
        db.delete(memory)
        db.commit()
        return True
    
    @staticmethod
    def update_processing_status(
        db: Session,
        memory_id: uuid.UUID,
        status: ProcessingStatus,
        error_message: Optional[str] = None
    ):
        """Update memory processing status"""
        memory = db.query(Memory).filter(Memory.id == memory_id).first()
        if memory:
            memory.status = status
            if error_message:
                memory.error_message = error_message
            db.commit()
