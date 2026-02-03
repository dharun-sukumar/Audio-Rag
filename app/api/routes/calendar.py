from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session
from datetime import date
from typing import Dict

from app.api.deps import get_current_user
from app.core.database import get_db
from app.models.user import User
from app.services.calendar import CalendarService
from app.schemas.calendar import CalendarDataResponse, CalendarDateRangeRequest

router = APIRouter(prefix="/calendar", tags=["calendar"])


@router.get("/date/{target_date}", response_model=CalendarDataResponse)
def get_calendar_data_by_date(
    target_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get all conversations and recordings for a specific date.
    
    This endpoint fetches both conversations and audio recordings created 
    on the specified date for the authenticated user.
    
    **Parameters:**
    - **target_date**: Date in YYYY-MM-DD format (e.g., 2026-02-03)
    
    **Returns:**
    - List of conversations with message counts
    - List of recordings with transcription status
    - Total count of items
    
    **Example:**
    ```
    GET /calendar/date/2026-02-03
    ```
    """
    try:
        calendar_data = CalendarService.get_calendar_data_for_date(
            db=db,
            user=user,
            target_date=target_date
        )
        return calendar_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendar data: {str(e)}"
        )


@router.post("/date-range", response_model=Dict[str, CalendarDataResponse])
def get_calendar_data_by_date_range(
    date_range: CalendarDateRangeRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get all conversations and recordings for a date range.
    
    This endpoint fetches both conversations and audio recordings created 
    within the specified date range for the authenticated user.
    Results are grouped by date.
    
    **Parameters:**
    - **start_date**: Start date in YYYY-MM-DD format
    - **end_date**: End date in YYYY-MM-DD format
    
    **Returns:**
    - Dictionary with date strings as keys
    - Each value contains conversations, recordings, and total count for that date
    
    **Example Request Body:**
    ```json
    {
        "start_date": "2026-02-01",
        "end_date": "2026-02-28"
    }
    ```
    """
    # Validate date range
    if date_range.start_date > date_range.end_date:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="start_date must be before or equal to end_date"
        )
    
    # Limit range to prevent excessive queries (e.g., max 90 days)
    date_diff = (date_range.end_date - date_range.start_date).days
    if date_diff > 90:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Date range cannot exceed 90 days"
        )
    
    try:
        calendar_data = CalendarService.get_calendar_data_for_date_range(
            db=db,
            user=user,
            start_date=date_range.start_date,
            end_date=date_range.end_date
        )
        return calendar_data
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch calendar data: {str(e)}"
        )


@router.get("/conversations/{target_date}")
def get_conversations_only(
    target_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get only conversations for a specific date.
    
    **Parameters:**
    - **target_date**: Date in YYYY-MM-DD format
    
    **Returns:**
    - List of conversations for the specified date
    """
    try:
        conversations = CalendarService.get_conversations_by_date(
            db=db,
            user=user,
            target_date=target_date
        )
        return {
            "date": target_date.isoformat(),
            "conversations": conversations,
            "count": len(conversations)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch conversations: {str(e)}"
        )


@router.get("/recordings/{target_date}")
def get_recordings_only(
    target_date: date,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user)
):
    """
    Get only recordings for a specific date.
    
    **Parameters:**
    - **target_date**: Date in YYYY-MM-DD format
    
    **Returns:**
    - List of recordings for the specified date
    """
    try:
        recordings = CalendarService.get_recordings_by_date(
            db=db,
            user=user,
            target_date=target_date
        )
        return {
            "date": target_date.isoformat(),
            "recordings": recordings,
            "count": len(recordings)
        }
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to fetch recordings: {str(e)}"
        )
