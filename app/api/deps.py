from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from sqlalchemy.dialects.postgresql import insert
from app.core.auth import verify_firebase_token, verify_firebase_token_optional
from app.core.database import get_db
from app.models.user import User


def normalize_email(email: str | None) -> str | None:
    """Normalize email to lowercase and strip whitespace."""
    return email.strip().lower() if email else None

def get_current_user(
    token_data: dict = Depends(verify_firebase_token_optional),
    x_guest_id: str = Header(None, alias="X-Guest-ID"),
    db: Session = Depends(get_db)
):
    """
    Get or create user from Firebase token or Guest ID.
    
    Priority:
    1. Firebase Token (Authenticated User)
    2. X-Guest-ID Header (Guest User)
    """
    user = None
    
    # 1. Handle Authenticated User (Firebase Token)
    if token_data:
        email = normalize_email(token_data.get("email"))
        firebase_uid = token_data["uid"]
        
        # Use UPSERT to handle race conditions
        # Try to find existing user first
        user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
        
        if not user and email:
            # Check by email (handle UID changes)
            user = db.query(User).filter(User.email == email).first()
        
        if user:
            # Update existing user
            user.firebase_uid = firebase_uid
            user.email = email or user.email
            user.name = token_data.get("name") or user.name
            user.picture = token_data.get("picture") or user.picture
            user.is_guest = False
            user.guest_id = None  # Clear guest_id on authenticated users
            user.last_seen_at = func.now()
            db.commit()
            db.refresh(user)
        else:
            # Create new user with race condition handling
            try:
                user = User(
                    firebase_uid=firebase_uid,
                    email=email,
                    name=token_data.get("name"),
                    picture=token_data.get("picture"),
                    is_guest=False,
                    guest_id=None,
                    last_seen_at=func.now()
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            except Exception as e:
                # Handle race condition - another request created the user
                db.rollback()
                user = db.query(User).filter(User.firebase_uid == firebase_uid).first()
                if not user and email:
                    user = db.query(User).filter(User.email == email).first()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create or retrieve user account"
                    )
                # Update the found user
                user.firebase_uid = firebase_uid
                user.email = email or user.email
                user.name = token_data.get("name") or user.name
                user.picture = token_data.get("picture") or user.picture
                user.is_guest = False
                user.guest_id = None
                user.last_seen_at = func.now()
                db.commit()
                db.refresh(user)
        
        return user

    # 2. Handle Guest User (X-Guest-ID)
    elif x_guest_id:
        # Look up guest user
        user = db.query(User).filter(
            User.guest_id == x_guest_id
        ).first()
        
        # Security check BEFORE any modifications
        if user and not user.is_guest:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid guest access to authenticated account"
            )
        
        if not user:
            # Create new guest user
            try:
                user = User(
                    guest_id=x_guest_id,
                    is_guest=True,
                    name="Guest",
                    last_seen_at=func.now()
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            except Exception as e:
                # Handle possible race condition if guest_id just created
                db.rollback()
                user = db.query(User).filter(User.guest_id == x_guest_id).first()
                if not user:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="Failed to create guest user"
                    )
        else:
            # Update last seen
            user.last_seen_at = func.now()
            db.commit()

        return user

    # 3. No Identity
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed. Provide Bearer token or X-Guest-ID."
    )
