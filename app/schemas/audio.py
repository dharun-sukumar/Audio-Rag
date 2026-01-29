from pydantic import BaseModel

class AudioProcessRequest(BaseModel):
    audio_key: str  # e.g. audio/meeting.mp3

class UploadRequest(BaseModel):
    filename: str
    mime: str
