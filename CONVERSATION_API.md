# Conversation API Documentation

## Overview
The Conversation API allows users to create, manage, and retrieve conversations with messages. Each conversation belongs to a specific user and contains multiple messages with roles (user/assistant).

## Authentication
All endpoints require authentication via Google OAuth token in the Authorization header:
```
Authorization: Bearer <your-google-oauth-token>
```

## Endpoints

### 1. Create Conversation
**POST** `/conversations/`

Create a new conversation with optional initial messages.

**Request Body:**
```json
{
  "title": "My Conversation",
  "messages": [
    {
      "role": "user",
      "content": "Hello, how are you?"
    },
    {
      "role": "assistant",
      "content": "I'm doing well, thank you!"
    }
  ]
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "My Conversation",
  "created_at": "2026-02-02T06:18:00Z",
  "updated_at": "2026-02-02T06:18:00Z",
  "messages": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "user",
      "content": "Hello, how are you?",
      "created_at": "2026-02-02T06:18:00Z"
    },
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "assistant",
      "content": "I'm doing well, thank you!",
      "created_at": "2026-02-02T06:18:00Z"
    }
  ]
}
```

---

### 2. List Conversations
**GET** `/conversations/`

List all conversations for the authenticated user, ordered by most recently updated.

**Query Parameters:**
- `skip` (optional, default: 0) - Number of conversations to skip
- `limit` (optional, default: 100) - Maximum number of conversations to return

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "user_id": "uuid",
    "title": "My Conversation",
    "created_at": "2026-02-02T06:18:00Z",
    "updated_at": "2026-02-02T06:18:00Z",
    "message_count": 5
  },
  {
    "id": "uuid",
    "user_id": "uuid",
    "title": "Another Conversation",
    "created_at": "2026-02-01T10:30:00Z",
    "updated_at": "2026-02-01T11:45:00Z",
    "message_count": 3
  }
]
```

---

### 3. Get Conversation
**GET** `/conversations/{conversation_id}`

Retrieve a specific conversation with all its messages.

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "My Conversation",
  "created_at": "2026-02-02T06:18:00Z",
  "updated_at": "2026-02-02T06:18:00Z",
  "messages": [
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "user",
      "content": "Hello, how are you?",
      "created_at": "2026-02-02T06:18:00Z"
    },
    {
      "id": "uuid",
      "conversation_id": "uuid",
      "role": "assistant",
      "content": "I'm doing well, thank you!",
      "created_at": "2026-02-02T06:18:01Z"
    }
  ]
}
```

**Error Responses:**
- `404 Not Found` - Conversation not found or doesn't belong to user

---

### 4. Update Conversation
**PATCH** `/conversations/{conversation_id}`

Update a conversation's title.

**Request Body:**
```json
{
  "title": "Updated Title"
}
```

**Response:** `200 OK`
```json
{
  "id": "uuid",
  "user_id": "uuid",
  "title": "Updated Title",
  "created_at": "2026-02-02T06:18:00Z",
  "updated_at": "2026-02-02T06:20:00Z",
  "messages": [...]
}
```

**Error Responses:**
- `404 Not Found` - Conversation not found or doesn't belong to user

---

### 5. Delete Conversation
**DELETE** `/conversations/{conversation_id}`

Delete a conversation and all its messages.

**Response:** `204 No Content`

**Error Responses:**
- `404 Not Found` - Conversation not found or doesn't belong to user

---

### 6. Add Message to Conversation
**POST** `/conversations/{conversation_id}/messages`

Add a new message to an existing conversation.

**Request Body:**
```json
{
  "role": "user",
  "content": "What can you help me with?"
}
```

**Response:** `201 Created`
```json
{
  "id": "uuid",
  "conversation_id": "uuid",
  "role": "user",
  "content": "What can you help me with?",
  "created_at": "2026-02-02T06:25:00Z"
}
```

**Error Responses:**
- `404 Not Found` - Conversation not found or doesn't belong to user

---

### 7. Get Conversation Messages
**GET** `/conversations/{conversation_id}/messages`

Get all messages for a specific conversation.

**Query Parameters:**
- `skip` (optional, default: 0) - Number of messages to skip
- `limit` (optional, default: 100) - Maximum number of messages to return

**Response:** `200 OK`
```json
[
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "user",
    "content": "Hello!",
    "created_at": "2026-02-02T06:18:00Z"
  },
  {
    "id": "uuid",
    "conversation_id": "uuid",
    "role": "assistant",
    "content": "Hi there!",
    "created_at": "2026-02-02T06:18:01Z"
  }
]
```

**Error Responses:**
- `404 Not Found` - Conversation not found or doesn't belong to user

---

## Database Schema

### Conversations Table
```sql
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_conversations_user_id ON conversations(user_id);
```

### Messages Table
```sql
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

CREATE INDEX idx_messages_conversation_id ON messages(conversation_id);
```

## Usage Examples

### Example 1: Create a conversation and add messages
```python
import requests

headers = {"Authorization": "Bearer <token>"}

# Create conversation
response = requests.post(
    "http://localhost:8000/conversations/",
    headers=headers,
    json={
        "title": "RAG Discussion",
        "messages": [
            {"role": "user", "content": "What is RAG?"},
            {"role": "assistant", "content": "RAG stands for Retrieval-Augmented Generation..."}
        ]
    }
)
conversation = response.json()

# Add another message
requests.post(
    f"http://localhost:8000/conversations/{conversation['id']}/messages",
    headers=headers,
    json={"role": "user", "content": "Tell me more"}
)
```

### Example 2: List and retrieve conversations
```python
# List all conversations
response = requests.get(
    "http://localhost:8000/conversations/",
    headers=headers
)
conversations = response.json()

# Get specific conversation with messages
conversation_id = conversations[0]["id"]
response = requests.get(
    f"http://localhost:8000/conversations/{conversation_id}",
    headers=headers
)
conversation_detail = response.json()
```

### Example 3: Update and delete
```python
# Update conversation title
requests.patch(
    f"http://localhost:8000/conversations/{conversation_id}",
    headers=headers,
    json={"title": "New Title"}
)

# Delete conversation
requests.delete(
    f"http://localhost:8000/conversations/{conversation_id}",
    headers=headers
)
```

## Notes

- All timestamps are in UTC with timezone information
- Conversations are automatically ordered by `updated_at` (most recent first)
- Deleting a conversation cascades to delete all associated messages
- The `updated_at` field is automatically updated when messages are added
- Message roles should be either "user" or "assistant"
- All endpoints require valid authentication
