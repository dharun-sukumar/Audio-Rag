from pydantic import BaseModel
from uuid import UUID
from datetime import datetime

class DocumentOut(BaseModel):
    id: UUID
    filename: str
    status: str | None = None
    created_at: datetime

    class Config:
        from_attributes = True
