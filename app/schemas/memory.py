from pydantic import BaseModel, Field, field_validator
from typing import Optional, List
from datetime import datetime
from uuid import UUID
from app.models.memory import MediaType, ProcessingStatus


# ============ Tag Schemas ============

class TagBase(BaseModel):
    """Base schema for Tag"""
    name: str = Field(..., min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class TagCreate(TagBase):
    """Schema for creating a new tag"""
    pass


class TagUpdate(BaseModel):
    """Schema for updating a tag"""
    name: Optional[str] = Field(None, min_length=1, max_length=100)
    color: Optional[str] = Field(None, pattern=r'^#[0-9A-Fa-f]{6}$')


class TagResponse(TagBase):
    """Schema for tag response"""
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    memory_count: Optional[int] = 0  # Number of memories with this tag

    class Config:
        from_attributes = True


# ============ Memory Schemas ============

class MemoryBase(BaseModel):
    """Base schema for Memory"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    mood: Optional[int] = Field(None, ge=1, le=5)
    people: Optional[List[str]] = []
    memory_date: Optional[datetime] = None


class MemoryCreate(MemoryBase):
    """Schema for creating a new memory (used with file upload)"""
    tag_ids: Optional[List[UUID]] = []
    
    @field_validator('people')
    @classmethod
    def validate_people(cls, v):
        if v is None:
            return []
        return v


class MemoryUpdate(BaseModel):
    """Schema for updating a memory"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    mood: Optional[int] = Field(None, ge=1, le=5)
    people: Optional[List[str]] = None
    tag_ids: Optional[List[UUID]] = None
    memory_date: Optional[datetime] = None


class MemoryResponse(MemoryBase):
    """Schema for memory response"""
    id: UUID
    user_id: UUID
    media_type: MediaType
    source_key: str
    audio_key: Optional[str] = None
    transcript_key: Optional[str] = None
    status: ProcessingStatus
    error_message: Optional[str] = None
    created_at: datetime
    updated_at: datetime
    tags: List[TagResponse] = []

    class Config:
        from_attributes = True


class MemoryListResponse(BaseModel):
    """Schema for paginated memory list response"""
    items: List[MemoryResponse]
    total: int
    page: int
    page_size: int
    total_pages: int


class MemoryFilterParams(BaseModel):
    """Schema for memory filtering parameters"""
    media_type: Optional[MediaType] = None
    topic: Optional[str] = None
    mood: Optional[int] = Field(None, ge=1, le=5)
    tag_ids: Optional[List[UUID]] = None
    status: Optional[ProcessingStatus] = None
    search: Optional[str] = None  # Search in title and description
    start_date: Optional[datetime] = None
    end_date: Optional[datetime] = None


# ============ Upload Schemas ============

class MemoryUploadMetadata(BaseModel):
    """Metadata for memory upload"""
    title: Optional[str] = Field(None, max_length=255)
    description: Optional[str] = None
    topic: Optional[str] = Field(None, max_length=100)
    mood: Optional[int] = Field(None, ge=1, le=5)
    people: Optional[List[str]] = []
    tag_ids: Optional[List[UUID]] = []
    memory_date: Optional[datetime] = None
