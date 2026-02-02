from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.schemas.conversation import (
    ConversationCreate,
    ConversationUpdate,
    ConversationResponse,
    ConversationListResponse,
    ConversationWithMessagesCreate,
    AddMessageRequest,
    MessageResponse
)

router = APIRouter(prefix="/conversations", tags=["conversations"])


@router.post("/", response_model=ConversationResponse, status_code=status.HTTP_201_CREATED)
def create_conversation(
    conversation_data: ConversationWithMessagesCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Create a new conversation for the authenticated user.
    Optionally include initial messages.
    """
    # Create the conversation
    conversation = Conversation(
        user_id=user.id,
        title=conversation_data.title
    )
    db.add(conversation)
    db.flush()  # Get the conversation ID before adding messages

    # Add initial messages if provided
    for msg_data in conversation_data.messages:
        message = Message(
            conversation_id=conversation.id,
            role=msg_data.role,
            content=msg_data.content
        )
        db.add(message)

    db.commit()
    db.refresh(conversation)
    return conversation


@router.get("/", response_model=List[ConversationListResponse])
def list_conversations(
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    List all conversations for the authenticated user.
    Returns conversations ordered by most recently updated first.
    """
    conversations = (
        db.query(
            Conversation,
            func.count(Message.id).label("message_count")
        )
        .outerjoin(Message, Conversation.id == Message.conversation_id)
        .filter(Conversation.user_id == user.id)
        .group_by(Conversation.id)
        .order_by(Conversation.updated_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # Format the response
    result = []
    for conv, msg_count in conversations:
        conv_dict = {
            "id": conv.id,
            "user_id": conv.user_id,
            "title": conv.title,
            "created_at": conv.created_at,
            "updated_at": conv.updated_at,
            "message_count": msg_count
        }
        result.append(ConversationListResponse(**conv_dict))

    return result


@router.get("/{conversation_id}", response_model=ConversationResponse)
def get_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Retrieve a specific conversation with all its messages.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    return conversation


@router.patch("/{conversation_id}", response_model=ConversationResponse)
def update_conversation(
    conversation_id: UUID,
    conversation_update: ConversationUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Update a conversation's title.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Update only provided fields
    if conversation_update.title is not None:
        conversation.title = conversation_update.title

    db.commit()
    db.refresh(conversation)
    return conversation


@router.delete("/{conversation_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_conversation(
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Delete a conversation and all its messages.
    """
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    db.delete(conversation)
    db.commit()
    return None


@router.post("/{conversation_id}/messages", response_model=MessageResponse, status_code=status.HTTP_201_CREATED)
def add_message_to_conversation(
    conversation_id: UUID,
    message_data: AddMessageRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Add a new message to an existing conversation.
    """
    # Verify conversation exists and belongs to user
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    # Create the message
    message = Message(
        conversation_id=conversation_id,
        role=message_data.role,
        content=message_data.content
    )
    db.add(message)
    
    # Update conversation's updated_at timestamp
    conversation.updated_at = func.now()
    
    db.commit()
    db.refresh(message)
    return message


@router.get("/{conversation_id}/messages", response_model=List[MessageResponse])
def get_conversation_messages(
    conversation_id: UUID,
    skip: int = 0,
    limit: int = 100,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get all messages for a specific conversation.
    """
    # Verify conversation exists and belongs to user
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )

    if not conversation:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Conversation not found"
        )

    messages = (
        db.query(Message)
        .filter(Message.conversation_id == conversation_id)
        .order_by(Message.created_at.asc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    return messages
