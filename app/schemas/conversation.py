from pydantic import BaseModel, Field
from datetime import datetime
from uuid import UUID
from typing import List, Optional

# Message Schemas
class MessageBase(BaseModel):
    role: str = Field(..., description="Role of the message sender: 'user' or 'assistant'")
    content: str = Field(..., description="Content of the message")

class MessageCreate(MessageBase):
    pass

class MessageResponse(MessageBase):
    id: UUID
    conversation_id: UUID
    created_at: datetime

    class Config:
        from_attributes = True


# Conversation Schemas
class ConversationBase(BaseModel):
    title: str = Field(..., description="Title of the conversation")

class ConversationCreate(ConversationBase):
    pass

class ConversationUpdate(BaseModel):
    title: Optional[str] = Field(None, description="Updated title of the conversation")

class ConversationResponse(ConversationBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    messages: List[MessageResponse] = []

    class Config:
        from_attributes = True

class ConversationListResponse(ConversationBase):
    id: UUID
    user_id: UUID
    created_at: datetime
    updated_at: datetime
    message_count: int = 0

    class Config:
        from_attributes = True


# Request schemas for creating conversations with messages
class ConversationWithMessagesCreate(BaseModel):
    title: str = Field(..., description="Title of the conversation")
    messages: List[MessageCreate] = Field(default_factory=list, description="Initial messages for the conversation")

class AddMessageRequest(BaseModel):
    role: str = Field(..., description="Role of the message sender: 'user' or 'assistant'")
    content: str = Field(..., description="Content of the message")
