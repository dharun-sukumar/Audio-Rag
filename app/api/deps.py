from fastapi import Depends
from sqlalchemy.orm import Session
from app.core.auth import verify_google_token
from app.core.database import get_db
from app.models.user import User

def get_current_user(
    token_data: dict = Depends(verify_google_token),
    db: Session = Depends(get_db)
):
    # token_data is what verify_google_token returns (dict)
    
    user = db.query(User).filter(
        User.google_sub == token_data["user_id"]
    ).first()

    if not user:
        user = User(
            google_sub=token_data["user_id"],
            email=token_data["email"],
            name=token_data["name"],
            picture=token_data["picture"],
        )
        db.add(user)
        db.commit()
        db.refresh(user)

    return user
