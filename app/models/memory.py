from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Text, Table, Enum as SQLEnum, Float
from sqlalchemy.dialects.postgresql import UUID, ARRAY
from sqlalchemy.sql import func
from sqlalchemy.orm import relationship
from pgvector.sqlalchemy import Vector
from app.core.database import Base
import uuid
import enum


class MediaType(str, enum.Enum):
    """Enum for supported media types"""
    AUDIO = "audio"
    VIDEO = "video"
    TEXT = "text"


class ProcessingStatus(str, enum.Enum):
    """Enum for processing status"""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


# Association table for many-to-many relationship between memories and tags
memory_tags = Table(
    'memory_tags',
    Base.metadata,
    Column('memory_id', UUID(as_uuid=True), ForeignKey('memories.id', ondelete='CASCADE'), primary_key=True),
    Column('tag_id', UUID(as_uuid=True), ForeignKey('tags.id', ondelete='CASCADE'), primary_key=True)
)


class Tag(Base):
    """Tag model for categorizing memories"""
    __tablename__ = "tags"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    name = Column(String(100), nullable=False)
    color = Column(String(7), nullable=True)  # Hex color code (e.g., #FF5733)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    user = relationship("User", back_populates="tags")
    memories = relationship("Memory", secondary=memory_tags, back_populates="tags")


class Memory(Base):
    """Memory model for storing audio, video, and text memories"""
    __tablename__ = "memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    # Content metadata
    title = Column(String(255), nullable=True)
    description = Column(Text, nullable=True)
    media_type = Column(SQLEnum(MediaType), nullable=False)
    
    # Storage keys
    source_key = Column(String, nullable=False)  # Original file key in S3 (audio/video/text)
    audio_key = Column(String, nullable=True)  # Extracted audio for video files
    transcript_key = Column(String, nullable=True)  # Transcription JSON key
    
    # Memory attributes
    topic = Column(String(100), nullable=True)  # Main topic/category
    mood = Column(Integer, nullable=True)  # 1-5 scale
    people = Column(ARRAY(String), nullable=True, default=[])  # List of people mentioned/involved
    
    # Processing status
    status = Column(SQLEnum(ProcessingStatus), default=ProcessingStatus.PENDING)
    error_message = Column(Text, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    memory_date = Column(DateTime(timezone=True), nullable=True)  # When the memory actually occurred
    
    # Relationships
    user = relationship("User", back_populates="memories")
    tags = relationship("Tag", secondary=memory_tags, back_populates="memories")
    semantic_memory = relationship("SemanticMemory", back_populates="memory", uselist=False, cascade="all, delete-orphan")


class SemanticMemory(Base):
    """
    Distilled semantic memory snapshot.
    This is the long-term, abstracted memory used for RAG.
    """
    __tablename__ = "semantic_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    memory_id = Column(UUID(as_uuid=True), ForeignKey("memories.id", ondelete="CASCADE"), nullable=False)
    
    content = Column(Text, nullable=False)  # The 3-6 sentence snapshot
    emotion_weight = Column(Integer, nullable=True)  # 1-5
    keywords = Column(ARRAY(String), nullable=True)  # Extracted keywords/patterns
    
    # Embedding for RAG (3072 dims for text-embedding-3-large)
    embedding = Column(Vector(3072)) 
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    
    # Relationships
    user = relationship("User")
    memory = relationship("Memory", back_populates="semantic_memory")


class EntityMemory(Base):
    """
    Consolidated memory about a specific entity (person, place, etc.)
    """
    __tablename__ = "entity_memories"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    
    name = Column(String(255), nullable=False)
    entity_type = Column(String(50), nullable=True) # Person, Place, Theme
    summary = Column(Text, nullable=True)
    observation_count = Column(Integer, default=1)
    last_interaction = Column(DateTime(timezone=True), nullable=True)
    
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    
    # Relationships
    user = relationship("User")
