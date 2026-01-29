from pydantic import BaseModel

class TokenData(BaseModel):
    user_id: str
    email: str | None = None
    name: str | None = None
    picture: str | None = None
