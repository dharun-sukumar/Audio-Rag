from sqlalchemy.orm import Session
from sqlalchemy import func, and_, cast, Date
from datetime import date, datetime, time
from typing import List, Dict
from uuid import UUID

from app.models.conversation import Conversation, Message
from app.models.document import Document
from app.models.user import User
from app.schemas.calendar import (
    CalendarConversationItem,
    CalendarRecordingItem,
    CalendarDataResponse
)


class CalendarService:
    """Service class for calendar-related operations"""
    
    @staticmethod
    def get_conversations_by_date(
        db: Session,
        user: User,
        target_date: date
    ) -> List[CalendarConversationItem]:
        """
        Fetch all conversations created on a specific date for a user
        
        Args:
            db: Database session
            user: Authenticated user
            target_date: The date to filter conversations
            
        Returns:
            List of CalendarConversationItem objects
        """
        # Convert date to datetime range (start and end of day)
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)
        
        # Query conversations with message count
        conversations = (
            db.query(
                Conversation,
                func.count(Message.id).label("message_count")
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
            .filter(
                and_(
                    Conversation.user_id == user.id,
                    Conversation.created_at >= start_of_day,
                    Conversation.created_at <= end_of_day
                )
            )
            .group_by(Conversation.id)
            .order_by(Conversation.created_at.desc())
            .all()
        )
        
        # Format the response
        result = []
        for conv, msg_count in conversations:
            item = CalendarConversationItem(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count or 0
            )
            result.append(item)
        
        return result
    
    @staticmethod
    def get_recordings_by_date(
        db: Session,
        user: User,
        target_date: date
    ) -> List[CalendarRecordingItem]:
        """
        Fetch all recordings (audio documents) created on a specific date for a user
        
        Args:
            db: Database session
            user: Authenticated user
            target_date: The date to filter recordings
            
        Returns:
            List of CalendarRecordingItem objects
        """
        # Convert date to datetime range (start and end of day)
        start_of_day = datetime.combine(target_date, time.min)
        end_of_day = datetime.combine(target_date, time.max)
        
        # Query documents
        documents = (
            db.query(Document)
            .filter(
                and_(
                    Document.user_id == user.id,
                    Document.created_at >= start_of_day,
                    Document.created_at <= end_of_day
                )
            )
            .order_by(Document.created_at.desc())
            .all()
        )
        
        # Format the response
        result = []
        for doc in documents:
            item = CalendarRecordingItem(
                document_id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at,
                has_transcription=doc.transcript_key is not None,
                audio_key=doc.source_key
            )
            result.append(item)
        
        return result
    
    @staticmethod
    def get_calendar_data_for_date(
        db: Session,
        user: User,
        target_date: date
    ) -> CalendarDataResponse:
        """
        Fetch all calendar data (conversations and recordings) for a specific date
        
        Args:
            db: Database session
            user: Authenticated user
            target_date: The date to fetch data for
            
        Returns:
            CalendarDataResponse with conversations and recordings
        """
        conversations = CalendarService.get_conversations_by_date(db, user, target_date)
        recordings = CalendarService.get_recordings_by_date(db, user, target_date)
        
        return CalendarDataResponse(
            date=target_date,
            conversations=conversations,
            recordings=recordings,
            total_count=len(conversations) + len(recordings)
        )
    
    @staticmethod
    def get_calendar_data_for_date_range(
        db: Session,
        user: User,
        start_date: date,
        end_date: date
    ) -> Dict[str, CalendarDataResponse]:
        """
        Fetch calendar data for a date range
        
        Args:
            db: Database session
            user: Authenticated user
            start_date: Start of the date range
            end_date: End of the date range
            
        Returns:
            Dictionary with date strings as keys and CalendarDataResponse as values
        """
        # Query all conversations in range
        start_datetime = datetime.combine(start_date, time.min)
        end_datetime = datetime.combine(end_date, time.max)
        
        conversations = (
            db.query(
                cast(Conversation.created_at, Date).label("date"),
                Conversation,
                func.count(Message.id).label("message_count")
            )
            .outerjoin(Message, Conversation.id == Message.conversation_id)
            .filter(
                and_(
                    Conversation.user_id == user.id,
                    Conversation.created_at >= start_datetime,
                    Conversation.created_at <= end_datetime
                )
            )
            .group_by(cast(Conversation.created_at, Date), Conversation.id)
            .all()
        )
        
        # Query all recordings in range
        recordings = (
            db.query(
                cast(Document.created_at, Date).label("date"),
                Document
            )
            .filter(
                and_(
                    Document.user_id == user.id,
                    Document.created_at >= start_datetime,
                    Document.created_at <= end_datetime
                )
            )
            .all()
        )
        
        # Group by date
        result = {}
        
        # Group conversations
        for date_val, conv, msg_count in conversations:
            date_str = date_val.isoformat()
            if date_str not in result:
                result[date_str] = CalendarDataResponse(
                    date=date_val,
                    conversations=[],
                    recordings=[],
                    total_count=0
                )
            
            item = CalendarConversationItem(
                id=conv.id,
                title=conv.title,
                created_at=conv.created_at,
                updated_at=conv.updated_at,
                message_count=msg_count or 0
            )
            result[date_str].conversations.append(item)
        
        # Group recordings
        for date_val, doc in recordings:
            date_str = date_val.isoformat()
            if date_str not in result:
                result[date_str] = CalendarDataResponse(
                    date=date_val,
                    conversations=[],
                    recordings=[],
                    total_count=0
                )
            
            item = CalendarRecordingItem(
                document_id=doc.id,
                filename=doc.filename,
                status=doc.status,
                created_at=doc.created_at,
                has_transcription=doc.transcript_key is not None,
                audio_key=doc.source_key
            )
            result[date_str].recordings.append(item)
        
        # Update total counts
        for date_str in result:
            result[date_str].total_count = (
                len(result[date_str].conversations) + 
                len(result[date_str].recordings)
            )
        
        return result
