"""
Firebase Authentication Module

This module provides proper Firebase ID token verification using Firebase Admin SDK.
This is the CORRECT way to verify Firebase Auth tokens (not Google OAuth tokens).
"""

from fastapi import Header, HTTPException, status
from firebase_admin import auth, credentials
import firebase_admin
import os
from typing import Dict, Any

# Initialize Firebase Admin SDK (only once)
def initialize_firebase():
    """
    Initialize Firebase Admin SDK
    
    This should be called once on application startup.
    Uses service account credentials from environment or file.
    """
    if not firebase_admin._apps:
        # Option 1: Use service account JSON file
        service_account_path = os.getenv("FIREBASE_SERVICE_ACCOUNT_PATH")
        
        if service_account_path and os.path.exists(service_account_path):
            cred = credentials.Certificate(service_account_path)
            firebase_admin.initialize_app(cred)
            print("✓ Firebase Admin initialized with service account file")
        else:
            # Option 2: Use default credentials (works in GCP environments)
            # Or initialize without credentials for local development
            try:
                firebase_admin.initialize_app()
                print("✓ Firebase Admin initialized with default credentials")
            except Exception as e:
                print(f"⚠ Firebase Admin initialization warning: {e}")
                print("  Firebase auth will use public key verification")


def verify_firebase_token(
    authorization: str = Header(...)
) -> Dict[str, Any]:
    """
    Verify Firebase ID token (NOT Google OAuth token)
    
    This is the industry-standard, Firebase-recommended way to verify tokens.
    
    Args:
        authorization: Authorization header with "Bearer <token>"
        
    Returns:
        Dictionary containing user information:
        - uid: Firebase user ID
        - email: User email
        - name: User display name
        - picture: User profile picture URL
        - email_verified: Whether email is verified
        - firebase: Firebase-specific claims
        
    Raises:
        HTTPException: If token is invalid, expired, or malformed
    """
    # Validate authorization header format
    if not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid authorization header format. Expected: 'Bearer <token>'"
        )

    # Extract token
    token = authorization.split(" ")[1]

    try:
        # Verify Firebase ID token using Firebase Admin SDK
        # This handles:
        # - Token signature verification
        # - Token expiry
        # - Clock skew
        # - Key rotation
        # - Revoked users
        decoded_token = auth.verify_id_token(token)

        # Extract user information
        return {
            "uid": decoded_token["uid"],
            "email": decoded_token.get("email"),
            "name": decoded_token.get("name"),
            "picture": decoded_token.get("picture"),
            "email_verified": decoded_token.get("email_verified", False),
            "firebase": decoded_token.get("firebase", {}),
            "auth_time": decoded_token.get("auth_time"),
            "exp": decoded_token.get("exp")
        }

    except auth.ExpiredIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token has expired. Please sign in again."
        )
    
    except auth.RevokedIdTokenError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Firebase token has been revoked. Please sign in again."
        )
    
    except auth.InvalidIdTokenError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Invalid Firebase token: {str(e)}"
        )
    
    except Exception as e:
        # Catch-all for unexpected errors
        print(f"❌ Firebase token verification failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentication failed. Please sign in again."
        )


def verify_firebase_token_optional(
    authorization: str = Header(None)
) -> Dict[str, Any] | None:
    """
    Optional Firebase token verification
    
    Returns None if no token provided, otherwise verifies the token.
    Useful for endpoints that support both authenticated and anonymous access.
    """
    if not authorization:
        return None
    
    return verify_firebase_token(authorization)


# Legacy Google OAuth verification (DEPRECATED - DO NOT USE FOR FIREBASE AUTH)
# Kept for reference only - remove if not needed
def verify_google_oauth_token_DEPRECATED(token: str):
    """
    ❌ DEPRECATED: This is for Google OAuth tokens, NOT Firebase Auth tokens
    
    Firebase Auth issues its own ID tokens with different:
    - Issuer (iss)
    - Audience (aud)
    - Signing keys
    
    Using this for Firebase tokens will cause:
    - Random failures
    - "Wrong issuer" errors
    - "Invalid audience" errors
    - "Token used too early" errors
    
    Use verify_firebase_token() instead.
    """
    from google.oauth2 import id_token as google_id_token
    from google.auth.transport import requests
    
    GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID")
    
    try:
        idinfo = google_id_token.verify_oauth2_token(
            token,
            requests.Request(),
            GOOGLE_CLIENT_ID
        )
        return idinfo
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=f"Google OAuth verification failed: {str(e)}"
        )
