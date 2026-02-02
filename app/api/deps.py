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
        # Create new user
        user = User(
            firebase_uid=token_data["uid"],
            email=token_data.get("email"),
            name=token_data.get("name"),
            picture=token_data.get("picture"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
