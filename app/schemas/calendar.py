from pydantic import BaseModel, Field
from datetime import date, datetime
from uuid import UUID
from typing import List, Optional

# Calendar-specific conversation response (simplified for calendar view)
class CalendarConversationItem(BaseModel):
    """Simplified conversation data for calendar display"""
    id: UUID
    title: str
    created_at: datetime
    updated_at: datetime
    message_count: int = 0
    
    class Config:
        from_attributes = True


# Calendar-specific recording/audio response
class CalendarRecordingItem(BaseModel):
    """Simplified recording data for calendar display"""
    document_id: UUID
    filename: str
    status: str
    created_at: datetime
    has_transcription: bool
    audio_key: str
    duration_seconds: Optional[int] = None  # Can be added later if needed
    
    class Config:
        from_attributes = True


# Combined calendar data response
class CalendarDataResponse(BaseModel):
    """Combined response containing both conversations and recordings for a date"""
    date: date
    conversations: List[CalendarConversationItem] = Field(default_factory=list)
    recordings: List[CalendarRecordingItem] = Field(default_factory=list)
    total_count: int = Field(description="Total items (conversations + recordings)")
    
    class Config:
        from_attributes = True


# Date range request
class CalendarDateRangeRequest(BaseModel):
    """Request for fetching calendar data for a date range"""
    start_date: date
    end_date: date
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2026-02-01",
                "end_date": "2026-02-28"
            }
        }
