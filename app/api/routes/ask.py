from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session
from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.rag import ask

router = APIRouter()

@router.post("/ask")
async def ask_question(
    q: dict,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    return await ask(db=db, user=user, query=q["query"])
