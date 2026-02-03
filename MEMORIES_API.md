# Memories API Documentation

## Overview

The Memories API is a comprehensive system for storing, organizing, and retrieving audio, video, and text memories with intelligent tagging, transcription, and RAG (Retrieval-Augmented Generation) capabilities.

## Features

### ✨ Core Capabilities
- **Multi-format Support**: Audio, video, and text files
- **Automatic Transcription**: Speech-to-text with speaker diarization (powered by AssemblyAI)
- **Video Processing**: Automatic audio extraction from video files using ffmpeg
- **RAG Integration**: All content is indexed for semantic search and AI-powered queries
- **Smart Tagging**: User-defined tags with color coding for organization
- **Rich Metadata**: Topic, mood (1-5 scale), people, dates, and descriptions
- **Full CRUD Operations**: Create, read, update, and delete for both memories and tags
- **Pagination & Filtering**: Advanced search and filter capabilities

### 🎯 Use Cases
- Personal voice journals
- Meeting recordings with speaker identification
- Video diary with automatic transcription
- Text note-taking with AI-powered retrieval
- Memory organization and retrieval

---

## API Endpoints

### 📌 Tag Management

#### Create Tag
```http
POST /memories/tags
Content-Type: application/json

{
  "name": "Work Meetings",
  "color": "#FF5733"
}
```

#### List All Tags
```http
GET /memories/tags
```

**Response:**
```json
[
  {
    "id": "uuid",
    "name": "Work Meetings",
    "color": "#FF5733",
    "memory_count": 15,
    "created_at": "2026-02-03T10:00:00Z",
    "updated_at": "2026-02-03T10:00:00Z"
  }
]
```

#### Update Tag
```http
PATCH /memories/tags/{tag_id}
Content-Type: application/json

{
  "name": "Team Meetings",
  "color": "#00FF00"
}
```

#### Delete Tag
```http
DELETE /memories/tags/{tag_id}
```

---

### 🎙️ Memory Management

#### Upload Memory (File)
```http
POST /memories/upload
Content-Type: multipart/form-data

file: <audio/video/text file>
metadata: {
  "title": "Team Standup",
  "description": "Daily standup meeting discussion",
  "topic": "Project Alpha",
  "mood": 4,
  "people": ["Alice", "Bob", "Charlie"],
  "tag_ids": ["uuid1", "uuid2"],
  "memory_date": "2026-02-03T09:00:00Z"
}
```

**Supported File Types:**
- **Audio**: mp3, wav, m4a, aac, ogg, flac
- **Video**: mp4, mov, avi, mkv, webm
- **Text**: txt, md, json

**Processing Pipeline:**
1. File uploaded to object storage
2. Video files: Audio extracted via ffmpeg
3. Audio/Video: Transcribed with speaker diarization
4. All content: Indexed in vector store for RAG

#### Create Text Memory
```http
POST /memories/text
Content-Type: application/x-www-form-urlencoded

text_content=<your text content>
metadata={...}
```

#### List Memories (with Pagination & Filters)
```http
GET /memories?page=1&page_size=20&media_type=audio&mood=5&search=meeting&tag_ids=uuid1,uuid2
```

**Query Parameters:**
- `page` (default: 1): Page number
- `page_size` (default: 20, max: 100): Items per page
- `media_type`: Filter by `audio`, `video`, or `text`
- `topic`: Search in topic field
- `mood`: Filter by mood (1-5)
- `status_filter`: Filter by `pending`, `processing`, `completed`, `failed`
- `search`: Search in title, description, and topic
- `tag_ids`: Comma-separated tag UUIDs

**Response:**
```json
{
  "items": [
    {
      "id": "uuid",
      "title": "Team Standup",
      "description": "Daily standup...",
      "media_type": "audio",
      "topic": "Project Alpha",
      "mood": 4,
      "people": ["Alice", "Bob"],
      "status": "completed",
      "tags": [...],
      "source_key": "s3-key",
      "audio_key": "s3-audio-key",
      "transcript_key": "s3-transcript-key",
      "created_at": "2026-02-03T09:00:00Z",
      "updated_at": "2026-02-03T09:05:00Z",
      "memory_date": "2026-02-03T09:00:00Z"
    }
  ],
  "total": 150,
  "page": 1,
  "page_size": 20,
  "total_pages": 8
}
```

#### Get Single Memory
```http
GET /memories/{memory_id}
```

#### Update Memory
```http
PATCH /memories/{memory_id}
Content-Type: application/json

{
  "title": "Updated Title",
  "topic": "New Topic",
  "mood": 5,
  "people": ["Alice", "Bob", "Charlie"],
  "tag_ids": ["uuid1", "uuid2"]
}
```

#### Delete Memory
```http
DELETE /memories/{memory_id}
```
*Deletes memory record and all associated files from storage.*

#### Get Memory Transcript
```http
GET /memories/{memory_id}/transcript
```

**Response:**
```json
{
  "text": "Full transcription text...",
  "utterances": [
    {
      "text": "Hello everyone",
      "speaker": "A",
      "start": 0,
      "end": 1500
    },
    {
      "text": "Hi team",
      "speaker": "B",
      "start": 1600,
      "end": 2200
    }
  ],
  "words": [...],
  "audio_duration": 120.5
}
```

---

## Database Schema

### Memory Table
```sql
CREATE TABLE memories (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    title VARCHAR(255),
    description TEXT,
    media_type ENUM('audio', 'video', 'text'),
    source_key VARCHAR,
    audio_key VARCHAR,
    transcript_key VARCHAR,
    topic VARCHAR(100),
    mood INTEGER CHECK (mood >= 1 AND mood <= 5),
    people TEXT[],
    status ENUM('pending', 'processing', 'completed', 'failed'),
    error_message TEXT,
    created_at TIMESTAMP,
    updated_at TIMESTAMP,
    memory_date TIMESTAMP
);
```

### Tag Table
```sql
CREATE TABLE tags (
    id UUID PRIMARY KEY,
    user_id UUID REFERENCES users(id),
    name VARCHAR(100),
    color VARCHAR(7),
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### Memory-Tag Association
```sql
CREATE TABLE memory_tags (
    memory_id UUID REFERENCES memories(id),
    tag_id UUID REFERENCES tags(id),
    PRIMARY KEY (memory_id, tag_id)
);
```

---

## Error Handling

### Common Error Responses

**400 Bad Request**
```json
{
  "detail": "Unsupported file type: application/pdf"
}
```

**404 Not Found**
```json
{
  "detail": "Memory not found"
}
```

**500 Internal Server Error**
```json
{
  "detail": "Failed to process memory: transcription error"
}
```

---

## Processing Status

Memories go through several processing stages:

1. **PENDING**: Initial upload, queued for processing
2. **PROCESSING**: 
   - Video: Extracting audio
   - Audio/Video: Transcribing
   - All: Indexing in vector store
3. **COMPLETED**: Fully processed and searchable
4. **FAILED**: Processing error (see `error_message`)

---

## Best Practices

### 1. File Uploads
- Use appropriate file extensions
- Keep video files under 500MB for best performance
- Provide meaningful titles and descriptions

### 2. Tagging Strategy
- Create tags before uploading memories
- Use consistent naming (e.g., "Work", "Personal", "Ideas")
- Limit to 5-10 core tags for easier organization

### 3. Metadata
- Always set `memory_date` for accurate timeline views
- Use `mood` consistently (1=very negative, 5=very positive)
- Include `people` for better filtering and context

### 4. Search & Filtering
- Use `search` for full-text queries across title/description/topic
- Combine filters for precise results (e.g., `mood=5&topic=success`)
- Use pagination for large result sets

---

## Examples

### Example 1: Upload Audio Meeting Recording
```bash
curl -X POST http://localhost:8000/memories/upload \
  -F "file=@meeting.mp3" \
  -F 'metadata={"title":"Q1 Planning","topic":"Strategy","mood":4,"people":["Alice","Bob"],"tag_ids":["work-tag-uuid"]}'
```

### Example 2: Create Text Note
```bash
curl -X POST http://localhost:8000/memories/text \
  -d "text_content=Great idea: implement feature X" \
  -d 'metadata={"title":"Feature Idea","topic":"Product","mood":5,"tag_ids":["ideas-tag-uuid"]}'
```

### Example 3: Search Memories
```bash
curl "http://localhost:8000/memories?search=planning&mood=4&page=1&page_size=10"
```

---

## Future Enhancements

- [ ] Audio/video playback with synchronized transcript
- [ ] Sentiment analysis for automatic mood detection
- [ ] Named entity recognition for automatic people detection
- [ ] Multi-language support
- [ ] Export memories to various formats (PDF, HTML)
- [ ] Collaborative memories with sharing capabilities
