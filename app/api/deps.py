from fastapi import Depends, Header, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from app.core.auth import verify_firebase_token, verify_firebase_token_optional
from app.core.database import get_db
from app.models.user import User

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
        # Look up user by Firebase UID
        user = db.query(User).filter(
            User.firebase_uid == token_data["uid"]
        ).first()

        if not user:
            # Check if user exists by email (to handle UID changes or database inconsistencies)
            email = token_data.get("email")
            if email:
                email = email.strip().lower()
                user = db.query(User).filter(User.email == email).first()

            if user:
                # Update existing user's Firebase UID
                user.firebase_uid = token_data["uid"]
                user.name = token_data.get("name") or user.name
                user.picture = token_data.get("picture") or user.picture
                user.last_seen_at = func.now()
                db.add(user)
                db.commit()
                db.refresh(user)
            else:
                # Create new user
                try:
                    user = User(
                        firebase_uid=token_data["uid"],
                        email=email,
                        name=token_data.get("name"),
                        picture=token_data.get("picture"),
                        is_guest=False,
                        last_seen_at=func.now()
                    )
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                except Exception as e:
                    # Handle race condition or data inconsistency
                    db.rollback()
                    if email:
                        user = db.query(User).filter(User.email == email).first()
                        if user:
                            # If we found them on retry, update and return
                            user.firebase_uid = token_data["uid"]
                            user.name = token_data.get("name") or user.name
                            user.picture = token_data.get("picture") or user.picture
                            user.last_seen_at = func.now()
                            db.add(user)
                            db.commit()
                            db.refresh(user)
                            return user
                    # If we still fail, re-raise
                    raise e
        else:
            # Existing user found via UID, just update last_seen
            user.last_seen_at = func.now()
            db.commit()
            
        return user

    # 2. Handle Guest User (X-Guest-ID)
    elif x_guest_id:
        # Look up guest user
        user = db.query(User).filter(
            User.guest_id == x_guest_id
        ).first()
        
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
                    raise e
        else:
             # Update last seen
            user.last_seen_at = func.now()
            db.commit()

        if not user.is_guest:
             # Security check: Don't allow accessing a real account via guest_id
             # This shouldn't happen if logic is correct, but safe to check
             raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid guest access to authenticated account"
             )

        return user

    # 3. No Identity
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication failed. Provide Bearer token or X-Guest-ID."
    )
