from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api.routes import audio, ask, documents, conversations, calendar, memories
from sqlalchemy import text
from app.core.database import engine, Base
from app.core.auth import initialize_firebase



app = FastAPI(
    servers=[
        {"url": "http://localhost:8000", "description": "local"},
        {"url": "http://139.59.19.169", "description": "production"}
    ]
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(audio.router)
app.include_router(ask.router)
app.include_router(documents.router)
app.include_router(conversations.router)
app.include_router(calendar.router)
app.include_router(memories.router)


@app.on_event("startup")
def startup():
    with engine.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=engine)
    initialize_firebase()


@app.get("/")
def health_check():
    return {"status": "ok", "message": "RAG Backend is running"}

