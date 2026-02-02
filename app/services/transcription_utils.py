"""
Transcription utilities for handling transcription storage and retrieval

This module provides reusable functions for working with transcriptions
stored in object storage.
"""

from typing import Dict, Any, Optional
from datetime import datetime, timezone
from app.services.storage import upload_json_to_storage, download_json_from_storage


def generate_transcript_key(audio_key: str) -> str:
    """
    Generate a transcript storage key from an audio key
    
    Args:
        audio_key: The S3 key of the audio file (e.g., "audio/2024-01-01_meeting.mp3")
        
    Returns:
        The S3 key for the transcript (e.g., "transcripts/2024-01-01_meeting.json")
        
    Examples:
        >>> generate_transcript_key("audio/2024-01-01_meeting.mp3")
        'transcripts/2024-01-01_meeting.json'
        
        >>> generate_transcript_key("audio/subfolder/recording.wav")
        'transcripts/subfolder/recording.json'
    """
    # Extract filename from path
    filename = audio_key.split("/")[-1]
    
    # Remove extension
    base_name = filename.rsplit(".", 1)[0]
    
    # Preserve subfolder structure if any
    path_parts = audio_key.split("/")[1:-1]  # Skip 'audio' and filename
    
    if path_parts:
        subfolder = "/".join(path_parts)
        return f"transcripts/{subfolder}/{base_name}.json"
    else:
        return f"transcripts/{base_name}.json"


def save_transcription(
    audio_key: str,
    transcript_data: Dict[Any, Any],
    custom_key: Optional[str] = None
) -> str:
    """
    Save transcription data to object storage
    
    Args:
        audio_key: The S3 key of the audio file
        transcript_data: The transcription data to save
        custom_key: Optional custom key to use instead of auto-generated one
        
    Returns:
        The S3 key where the transcription was saved
        
    Raises:
        Exception: If upload fails
    """
    transcript_key = custom_key or generate_transcript_key(audio_key)
    
    # Add metadata
    enriched_data = {
        **transcript_data,
        "_metadata": {
            "audio_key": audio_key,
            "saved_at": datetime.now(timezone.utc).isoformat(),
            "version": "1.0"
        }
    }
    
    upload_json_to_storage(transcript_key, enriched_data)
    return transcript_key


def load_transcription(transcript_key: str) -> Dict[Any, Any]:
    """
    Load transcription data from object storage
    
    Args:
        transcript_key: The S3 key of the transcription
        
    Returns:
        The transcription data
        
    Raises:
        Exception: If download fails
    """
    return download_json_from_storage(transcript_key)


def get_transcript_text(transcript_data: Dict[Any, Any]) -> str:
    """
    Extract plain text from transcription data
    
    Args:
        transcript_data: The transcription data from AssemblyAI
        
    Returns:
        The full transcript as plain text
    """
    return transcript_data.get("text", "")


def get_transcript_words(transcript_data: Dict[Any, Any]) -> list:
    """
    Extract word-level timestamps from transcription data
    
    Args:
        transcript_data: The transcription data from AssemblyAI
        
    Returns:
        List of word objects with timestamps
    """
    return transcript_data.get("words", [])


def get_transcript_duration(transcript_data: Dict[Any, Any]) -> float:
    """
    Get the audio duration from transcription data
    
    Args:
        transcript_data: The transcription data from AssemblyAI
        
    Returns:
        Duration in seconds
    """
    return transcript_data.get("audio_duration", 0) / 1000.0  # Convert ms to seconds


def format_transcript_for_export(
    transcript_data: Dict[Any, Any],
    format_type: str = "text"
) -> str:
    """
    Format transcription for export in different formats
    
    Args:
        transcript_data: The transcription data
        format_type: Export format ('text', 'srt', 'vtt')
        
    Returns:
        Formatted transcript string
    """
    if format_type == "text":
        return get_transcript_text(transcript_data)
    
    elif format_type == "srt":
        # SRT subtitle format
        words = get_transcript_words(transcript_data)
        srt_lines = []
        
        for i, word in enumerate(words, 1):
            start_ms = word.get("start", 0)
            end_ms = word.get("end", 0)
            text = word.get("text", "")
            
            start_time = _ms_to_srt_time(start_ms)
            end_time = _ms_to_srt_time(end_ms)
            
            srt_lines.append(f"{i}")
            srt_lines.append(f"{start_time} --> {end_time}")
            srt_lines.append(text)
            srt_lines.append("")
        
        return "\n".join(srt_lines)
    
    elif format_type == "vtt":
        # WebVTT format
        words = get_transcript_words(transcript_data)
        vtt_lines = ["WEBVTT", ""]
        
        for word in words:
            start_ms = word.get("start", 0)
            end_ms = word.get("end", 0)
            text = word.get("text", "")
            
            start_time = _ms_to_vtt_time(start_ms)
            end_time = _ms_to_vtt_time(end_ms)
            
            vtt_lines.append(f"{start_time} --> {end_time}")
            vtt_lines.append(text)
            vtt_lines.append("")
        
        return "\n".join(vtt_lines)
    
    else:
        raise ValueError(f"Unsupported format: {format_type}")


def _ms_to_srt_time(milliseconds: int) -> str:
    """Convert milliseconds to SRT time format (HH:MM:SS,mmm)"""
    seconds = milliseconds / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(milliseconds % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d},{ms:03d}"


def _ms_to_vtt_time(milliseconds: int) -> str:
    """Convert milliseconds to WebVTT time format (HH:MM:SS.mmm)"""
    seconds = milliseconds / 1000
    hours = int(seconds // 3600)
    minutes = int((seconds % 3600) // 60)
    secs = int(seconds % 60)
    ms = int(milliseconds % 1000)
    return f"{hours:02d}:{minutes:02d}:{secs:02d}.{ms:03d}"


def search_transcript(
    transcript_data: Dict[Any, Any],
    query: str,
    case_sensitive: bool = False
) -> list:
    """
    Search for a query in the transcript and return matching segments
    
    Args:
        transcript_data: The transcription data
        query: The search query
        case_sensitive: Whether to perform case-sensitive search
        
    Returns:
        List of matching word objects with context
    """
    words = get_transcript_words(transcript_data)
    matches = []
    
    search_query = query if case_sensitive else query.lower()
    
    for i, word in enumerate(words):
        word_text = word.get("text", "")
        compare_text = word_text if case_sensitive else word_text.lower()
        
        if search_query in compare_text:
            # Include context (5 words before and after)
            context_start = max(0, i - 5)
            context_end = min(len(words), i + 6)
            context_words = words[context_start:context_end]
            
            matches.append({
                "word": word,
                "index": i,
                "context": " ".join([w.get("text", "") for w in context_words]),
                "timestamp": word.get("start", 0) / 1000  # Convert to seconds
            })
    
    return matches
