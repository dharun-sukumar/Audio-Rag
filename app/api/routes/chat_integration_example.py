"""
Integration Example: Conversation-aware RAG System

This example shows how to integrate the conversation API with the RAG system
to maintain conversation history while querying documents.
"""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import Optional
from uuid import UUID

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.models.conversation import Conversation, Message
from app.services.rag import ask
from app.schemas.conversation import ConversationResponse

router = APIRouter(prefix="/chat", tags=["chat"])


@router.post("/ask", response_model=ConversationResponse)
def ask_with_conversation(
    query: str,
    conversation_id: Optional[UUID] = None,
    conversation_title: Optional[str] = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Ask a question and save it to a conversation.
    
    - If conversation_id is provided, add to existing conversation
    - If conversation_id is None, create a new conversation
    - The RAG response is automatically saved as an assistant message
    """
    
    # Get or create conversation
    if conversation_id:
        # Use existing conversation
        conversation = (
            db.query(Conversation)
            .filter(
                Conversation.id == conversation_id,
                Conversation.user_id == user.id
            )
            .first()
        )
        
        if not conversation:
            raise HTTPException(status_code=404, detail="Conversation not found")
    else:
        # Create new conversation
        title = conversation_title or f"Conversation about: {query[:50]}..."
        conversation = Conversation(
            user_id=user.id,
            title=title
        )
        db.add(conversation)
        db.flush()
    
    # Save user's question
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=query
    )
    db.add(user_message)
    db.flush()
    
    # Get RAG response
    rag_response = ask(db=db, user=user, query=query)
    
    # Save assistant's response
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=rag_response.get("answer", "")
    )
    db.add(assistant_message)
    
    # Commit all changes
    db.commit()
    db.refresh(conversation)
    
    # Return the conversation with all messages
    return conversation


@router.post("/ask-with-history", response_model=dict)
def ask_with_conversation_history(
    query: str,
    conversation_id: UUID,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Ask a question with full conversation history context.
    
    This endpoint retrieves the conversation history and includes it
    in the RAG query for better context-aware responses.
    """
    
    # Get conversation with messages
    conversation = (
        db.query(Conversation)
        .filter(
            Conversation.id == conversation_id,
            Conversation.user_id == user.id
        )
        .first()
    )
    
    if not conversation:
        raise HTTPException(status_code=404, detail="Conversation not found")
    
    # Build context from conversation history
    history_context = []
    for msg in conversation.messages[-5:]:  # Last 5 messages for context
        history_context.append(f"{msg.role}: {msg.content}")
    
    # Combine history with current query
    context_aware_query = "\n".join(history_context + [f"user: {query}"])
    
    # Save user's question
    user_message = Message(
        conversation_id=conversation.id,
        role="user",
        content=query
    )
    db.add(user_message)
    db.flush()
    
    # Get RAG response with history context
    rag_response = ask(db=db, user=user, query=context_aware_query)
    
    # Save assistant's response
    assistant_message = Message(
        conversation_id=conversation.id,
        role="assistant",
        content=rag_response.get("answer", "")
    )
    db.add(assistant_message)
    
    db.commit()
    
    return {
        "conversation_id": conversation.id,
        "query": query,
        "answer": rag_response.get("answer", ""),
        "sources": rag_response.get("sources", []),
        "message_id": str(assistant_message.id)
    }


# Example usage in your frontend:
"""
// Create a new conversation
const response = await fetch('/chat/ask', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: 'What is in my audio files?',
    conversation_title: 'Audio Analysis Discussion'
  })
});

const conversation = await response.json();
const conversationId = conversation.id;

// Continue the conversation
const followUp = await fetch('/chat/ask', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: 'Tell me more about the first file',
    conversation_id: conversationId
  })
});

// Or use history-aware endpoint
const historyResponse = await fetch('/chat/ask-with-history', {
  method: 'POST',
  headers: {
    'Authorization': `Bearer ${token}`,
    'Content-Type': 'application/json'
  },
  body: JSON.stringify({
    query: 'Can you summarize what we discussed?',
    conversation_id: conversationId
  })
});
"""
