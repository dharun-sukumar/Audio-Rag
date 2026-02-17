from fastapi import APIRouter, Depends, HTTPException, status, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import text
from typing import Dict, Any

from app.api.deps import get_db
from app.core.auth import verify_firebase_token
from app.models.user import User
from app.models.conversation import Conversation
from app.models.memory import Memory, Tag, memory_tags
from pydantic import BaseModel

router = APIRouter(prefix="/auth", tags=["auth"])

class MergeGuestRequest(BaseModel):
    guest_id: str

@router.post("/merge-guest")
def merge_guest_account(
    request: MergeGuestRequest,
    token_data: Dict[str, Any] = Depends(verify_firebase_token),
    db: Session = Depends(get_db)
):
    """
    Merge a guest account into the authenticated user's account.
    
    This moves all data (conversations, memories, tags) from the guest user
    identified by `guest_id` to the currently logged-in Firebase user.
    """
    firebase_uid = token_data["uid"]
    
    # 1. Get Current User
    current_user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
    if not current_user:
        # Fallback to email lookup if necessary
        from app.api.deps import normalize_email
        email = normalize_email(token_data.get("email"))
        if email:
             current_user = db.query(User).filter(User.email == email).first()
    
    if not current_user:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Authenticated user record not found"
        )

    # 2. Get Guest User
    guest_user = db.query(User).filter(
        User.guest_id == request.guest_id
    ).first()
    
    # Handle edge cases with idempotency
    if not guest_user:
        # Guest already merged or doesn't exist - return success (idempotent)
        return {"status": "success", "message": "Merge completed"}
    
    if guest_user.id == current_user.id:
        # Same user - just clear guest_id and return success
        current_user.guest_id = None
        current_user.is_guest = False
        db.commit()
        return {"status": "success", "message": "Guest account upgraded"}
        
    if not guest_user.is_guest:
        # Security check: don't merge another real user
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Cannot merge authenticated accounts"
        )

    # 3. Transactional Merge
    try:
        # Set transaction isolation level for consistency
        db.execute(text("SET TRANSACTION ISOLATION LEVEL SERIALIZABLE"))
        
        # A. Move Conversations
        # Update user_id for all conversations belonging to guest
        conversations = db.query(Conversation).filter(Conversation.user_id == guest_user.id).all()
        for conv in conversations:
            conv.user_id = current_user.id
            
        # B. Move Memories
        memories = db.query(Memory).filter(Memory.user_id == guest_user.id).all()
        for mem in memories:
            mem.user_id = current_user.id

        # C. Handle Tags (Merge Strategy)
        # We need to be careful about unique constraints on (user_id, name)
        guest_tags = db.query(Tag).filter(Tag.user_id == guest_user.id).all()
        
        for guest_tag in guest_tags:
            # Check if current_user already has a tag with this name
            existing_tag = db.query(Tag).filter(
                Tag.user_id == current_user.id,
                Tag.name == guest_tag.name
            ).first()
            
            if existing_tag:
                # Conflict! 
                # We must move all memories that use guest_tag to use existing_tag instead.
                # guest_tag.memories is a relationship.
                # We need to re-assign these memories to existing_tag.
                
                # Iterate over memories associated with the guest_tag
                # We can't modify the collection while iterating safely sometimes, so copy list
                associated_memories = list(guest_tag.memories)
                for memory in associated_memories:
                    # Add existing_tag to memory if not present
                    if existing_tag not in memory.tags:
                        memory.tags.append(existing_tag)
                    # Remove guest_tag
                    if guest_tag in memory.tags:
                        memory.tags.remove(guest_tag)
                
                # Now guest_tag has no memories, we can delete it
                db.delete(guest_tag)
            else:
                # No conflict, just transfer ownership
                guest_tag.user_id = current_user.id
        
        # D. Clear guest_id from current user if set
        if current_user.guest_id:
            current_user.guest_id = None
        current_user.is_guest = False
        
        # E. Delete Guest User
        db.delete(guest_user)
        
        db.commit()
        return {"status": "success", "message": "Account merged successfully"}
        
    except Exception as e:
        db.rollback()
        import traceback
        error_details = traceback.format_exc()
        print(f"Merge error: {e}\n{error_details}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to merge account data. Please try again."
        )
