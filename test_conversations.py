"""
Test script for conversation endpoints

This script demonstrates how to use the conversation API endpoints.
Make sure to replace the token with a valid Google OAuth token.
"""

import requests
import json

BASE_URL = "http://localhost:8000"

# You'll need a valid Google OAuth token for testing
# Replace this with your actual token
TOKEN = "your-google-oauth-token-here"

headers = {
    "Authorization": f"Bearer {TOKEN}",
    "Content-Type": "application/json"
}


def test_create_conversation():
    """Create a new conversation with initial messages"""
    data = {
        "title": "My First Conversation",
        "messages": [
            {
                "role": "user",
                "content": "Hello, how can I analyze my audio files?"
            },
            {
                "role": "assistant",
                "content": "I can help you analyze audio files. You can upload them and I'll process them for you."
            }
        ]
    }
    
    response = requests.post(
        f"{BASE_URL}/conversations/",
        headers=headers,
        json=data
    )
    
    print("Create Conversation Response:")
    print(json.dumps(response.json(), indent=2, default=str))
    return response.json()


def test_list_conversations():
    """List all conversations"""
    response = requests.get(
        f"{BASE_URL}/conversations/",
        headers=headers
    )
    
    print("\nList Conversations Response:")
    print(json.dumps(response.json(), indent=2, default=str))
    return response.json()


def test_get_conversation(conversation_id):
    """Get a specific conversation with all messages"""
    response = requests.get(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=headers
    )
    
    print(f"\nGet Conversation {conversation_id} Response:")
    print(json.dumps(response.json(), indent=2, default=str))
    return response.json()


def test_add_message(conversation_id):
    """Add a message to a conversation"""
    data = {
        "role": "user",
        "content": "Can you tell me more about the RAG system?"
    }
    
    response = requests.post(
        f"{BASE_URL}/conversations/{conversation_id}/messages",
        headers=headers,
        json=data
    )
    
    print(f"\nAdd Message to Conversation {conversation_id} Response:")
    print(json.dumps(response.json(), indent=2, default=str))
    return response.json()


def test_update_conversation(conversation_id):
    """Update conversation title"""
    data = {
        "title": "Updated Conversation Title"
    }
    
    response = requests.patch(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=headers,
        json=data
    )
    
    print(f"\nUpdate Conversation {conversation_id} Response:")
    print(json.dumps(response.json(), indent=2, default=str))
    return response.json()


def test_delete_conversation(conversation_id):
    """Delete a conversation"""
    response = requests.delete(
        f"{BASE_URL}/conversations/{conversation_id}",
        headers=headers
    )
    
    print(f"\nDelete Conversation {conversation_id} Response:")
    print(f"Status Code: {response.status_code}")


if __name__ == "__main__":
    print("=" * 60)
    print("Conversation API Test Suite")
    print("=" * 60)
    
    # Note: You need to set a valid token above to run these tests
    if TOKEN == "your-google-oauth-token-here":
        print("\n⚠️  Please set a valid Google OAuth token in the TOKEN variable")
        print("You can get this from your frontend application after logging in")
    else:
        # Run the test flow
        conv = test_create_conversation()
        conv_id = conv.get("id")
        
        if conv_id:
            test_list_conversations()
            test_get_conversation(conv_id)
            test_add_message(conv_id)
            test_update_conversation(conv_id)
            # Uncomment to test deletion
            # test_delete_conversation(conv_id)
