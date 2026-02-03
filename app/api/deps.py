from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.auth import verify_firebase_token
from app.core.database import get_db
from app.models.user import User

def get_current_user(
    token_data: dict = Depends(verify_firebase_token),
    db: Session = Depends(get_db)
):
    """
    Get or create user from Firebase token
    
    Uses Firebase UID as the primary identifier (not Google sub).
    """
    # token_data contains: uid, email, name, picture, email_verified, firebase
    
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
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            except Exception as e:
                # Handle race condition or data inconsistency where email exists but wasn't found
                # (e.g., race condition or weird casing issues)
                db.rollback()
                if email:
                    user = db.query(User).filter(User.email == email).first()
                    if user:
                        user.firebase_uid = token_data["uid"]
                        user.name = token_data.get("name") or user.name
                        user.picture = token_data.get("picture") or user.picture
                        db.add(user)
                        db.commit()
                        db.refresh(user)
                        return user
                # If we still fail, re-raise
                raise e

    return user
