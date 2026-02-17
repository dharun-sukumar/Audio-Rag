# Frontend Authentication Integration Guide

**Last Updated:** February 9, 2026  
**API Version:** 1.0  
**Backend:** FastAPI + Firebase Authentication

---

## Table of Contents
1. [Overview](#overview)
2. [Guest User Flow](#guest-user-flow)
3. [Authenticated User Flow](#authenticated-user-flow)
4. [Guest to Authenticated Transition](#guest-to-authenticated-transition)
5. [API Reference](#api-reference)
6. [Code Examples](#code-examples)
7. [Error Handling](#error-handling)
8. [Best Practices](#best-practices)

---

## Overview

The application supports **two authentication modes**:

| Mode | Identifier | Use Case | Limitations |
|------|-----------|----------|-------------|
| **Guest** | `X-Guest-ID` header | Anonymous users, trial experience | 3 conversations max |
| **Authenticated** | Firebase ID Token | Full access | No limits |

### Key Concepts

- **Guest users** are temporary, identified by a client-generated UUID
- **Authenticated users** use Firebase Authentication (Google, Email/Password, etc.)
- **Guest data can be merged** into authenticated accounts seamlessly
- **All API endpoints** accept either authentication method

---

## Guest User Flow

### 1. Generate Guest ID

When a user first visits your app without signing in, generate a unique guest ID:

```javascript
// Generate once and store in localStorage
function getOrCreateGuestId() {
  let guestId = localStorage.getItem('guestId');
  
  if (!guestId) {
    guestId = crypto.randomUUID(); // e.g., "550e8400-e29b-41d4-a716-446655440000"
    localStorage.setItem('guestId', guestId);
  }
  
  return guestId;
}
```

### 2. Make API Requests

Include the `X-Guest-ID` header in all API requests:

```javascript
const guestId = getOrCreateGuestId();

const response = await fetch('https://your-api.com/conversations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'X-Guest-ID': guestId  // Required for guest users
  },
  body: JSON.stringify({
    title: 'My First Conversation'
  })
});
```

### 3. Guest Limitations

Guests are limited to **3 conversations**. When the limit is reached:

```json
{
  "detail": "Guest limit reached. Please log in to continue."
}
```

**Frontend Response:**
- Show a "Sign in to continue" modal
- Preserve the guest ID for later merging
- Prompt user to authenticate

---

## Authenticated User Flow

### 1. Firebase Authentication Setup

```javascript
// Initialize Firebase
import { initializeApp } from 'firebase/app';
import { getAuth, signInWithPopup, GoogleAuthProvider } from 'firebase/auth';

const firebaseConfig = {
  apiKey: "YOUR_API_KEY",
  authDomain: "YOUR_AUTH_DOMAIN",
  projectId: "YOUR_PROJECT_ID",
  // ... other config
};

const app = initializeApp(firebaseConfig);
const auth = getAuth(app);
```

### 2. Sign In and Get ID Token

```javascript
async function signInWithGoogle() {
  const provider = new GoogleAuthProvider();
  
  try {
    const result = await signInWithPopup(auth, provider);
    const user = result.user;
    
    // Get the Firebase ID token
    const idToken = await user.getIdToken();
    
    // Store for API requests
    localStorage.setItem('firebaseToken', idToken);
    
    return { user, idToken };
  } catch (error) {
    console.error('Sign in error:', error);
    throw error;
  }
}
```

### 3. Make Authenticated API Requests

```javascript
const idToken = localStorage.getItem('firebaseToken');

const response = await fetch('https://your-api.com/conversations', {
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Authorization': `Bearer ${idToken}`  // Firebase ID token
  },
  body: JSON.stringify({
    title: 'My Authenticated Conversation'
  })
});
```

### 4. Token Refresh

Firebase tokens expire after 1 hour. Refresh automatically:

```javascript
import { onAuthStateChanged } from 'firebase/auth';

onAuthStateChanged(auth, async (user) => {
  if (user) {
    // User is signed in, get fresh token
    const idToken = await user.getIdToken(/* forceRefresh */ true);
    localStorage.setItem('firebaseToken', idToken);
  } else {
    // User is signed out
    localStorage.removeItem('firebaseToken');
  }
});
```

---

## Guest to Authenticated Transition

When a guest user signs in, merge their guest data into their new authenticated account.

### Flow Diagram

```
1. User is browsing as guest (has guestId in localStorage)
2. User clicks "Sign In" → Firebase authentication
3. Get Firebase ID token
4. Call /auth/merge-guest endpoint
5. Guest data (conversations, memories, tags) → Authenticated account
6. Clear guest ID from localStorage
7. Continue using authenticated session
```

### Implementation

```javascript
async function handleSignIn() {
  const guestId = localStorage.getItem('guestId');
  
  // Step 1: Sign in with Firebase
  const { user, idToken } = await signInWithGoogle();
  
  // Step 2: Merge guest data if exists
  if (guestId) {
    try {
      const mergeResponse = await fetch('https://your-api.com/auth/merge-guest', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'Authorization': `Bearer ${idToken}`
        },
        body: JSON.stringify({
          guest_id: guestId
        })
      });
      
      const result = await mergeResponse.json();
      console.log('Merge result:', result);
      // { "status": "success", "message": "Account merged successfully" }
      
      // Step 3: Clean up guest ID
      localStorage.removeItem('guestId');
      
    } catch (error) {
      console.error('Merge failed:', error);
      // Even if merge fails, user is still authenticated
      // Guest data might already be merged or not exist
    }
  }
  
  // Step 4: Store token and redirect
  localStorage.setItem('firebaseToken', idToken);
  // Redirect to main app or refresh UI
}
```

### Important Notes

- **Idempotent Operation**: Calling merge multiple times is safe
- **Already Merged**: Returns success even if guest was already merged
- **No Guest Data**: Returns success if guest_id doesn't exist
- **Error Handling**: If merge fails, user is still authenticated

---

## API Reference

### Authentication Headers

| Scenario | Header | Value | Priority |
|----------|--------|-------|----------|
| Guest User | `X-Guest-ID` | UUID string | 2 |
| Authenticated | `Authorization` | `Bearer <firebase_token>` | 1 |

**Priority:** If both headers are present, `Authorization` takes precedence.

### Endpoints

#### All Protected Endpoints

**Headers Required:** ONE of the following:
- `Authorization: Bearer <firebase_id_token>`
- `X-Guest-ID: <guest_uuid>`

**Examples:**
- `GET /conversations` - List conversations
- `POST /conversations` - Create conversation
- `GET /memories` - List memories
- `POST /memories/upload` - Upload memory
- `POST /audio/transcribe` - Transcribe audio
- `GET /memories/tags` - List tags

#### Merge Guest Account

```http
POST /auth/merge-guest
Authorization: Bearer <firebase_id_token>
Content-Type: application/json

{
  "guest_id": "550e8400-e29b-41d4-a716-446655440000"
}
```

**Response (Success):**
```json
{
  "status": "success",
  "message": "Account merged successfully"
}
```

**Response (Idempotent - Already Merged):**
```json
{
  "status": "success",
  "message": "Merge completed"
}
```

**Response (Error):**
```json
{
  "detail": "Cannot merge authenticated accounts"
}
```

---

## Code Examples

### React Hook for Authentication

```javascript
import { useState, useEffect } from 'react';
import { getAuth, onAuthStateChanged } from 'firebase/auth';

export function useAuth() {
  const [user, setUser] = useState(null);
  const [token, setToken] = useState(null);
  const [loading, setLoading] = useState(true);
  
  useEffect(() => {
    const auth = getAuth();
    
    const unsubscribe = onAuthStateChanged(auth, async (firebaseUser) => {
      if (firebaseUser) {
        const idToken = await firebaseUser.getIdToken();
        setUser(firebaseUser);
        setToken(idToken);
      } else {
        setUser(null);
        setToken(null);
      }
      setLoading(false);
    });
    
    return () => unsubscribe();
  }, []);
  
  return { user, token, loading };
}
```

### API Client with Auto-Authentication

```javascript
class ApiClient {
  constructor(baseURL) {
    this.baseURL = baseURL;
  }
  
  async getHeaders() {
    const headers = {
      'Content-Type': 'application/json'
    };
    
    // Try authenticated token first
    const token = localStorage.getItem('firebaseToken');
    if (token) {
      headers['Authorization'] = `Bearer ${token}`;
      return headers;
    }
    
    // Fall back to guest ID
    const guestId = localStorage.getItem('guestId');
    if (guestId) {
      headers['X-Guest-ID'] = guestId;
      return headers;
    }
    
    // No authentication
    throw new Error('No authentication available');
  }
  
  async request(endpoint, options = {}) {
    const headers = await this.getHeaders();
    
    const response = await fetch(`${this.baseURL}${endpoint}`, {
      ...options,
      headers: {
        ...headers,
        ...options.headers
      }
    });
    
    if (!response.ok) {
      const error = await response.json();
      throw new Error(error.detail || 'Request failed');
    }
    
    return response.json();
  }
  
  // Convenience methods
  get(endpoint) {
    return this.request(endpoint, { method: 'GET' });
  }
  
  post(endpoint, data) {
    return this.request(endpoint, {
      method: 'POST',
      body: JSON.stringify(data)
    });
  }
  
  patch(endpoint, data) {
    return this.request(endpoint, {
      method: 'PATCH',
      body: JSON.stringify(data)
    });
  }
  
  delete(endpoint) {
    return this.request(endpoint, { method: 'DELETE' });
  }
}

// Usage
const api = new ApiClient('https://your-api.com');

// Create conversation (works for both guest and authenticated)
const conversation = await api.post('/conversations', {
  title: 'My Conversation',
  messages: []
});
```

### Complete Sign-In Component (React)

```jsx
import { useState } from 'react';
import { getAuth, signInWithPopup, GoogleAuthProvider } from 'firebase/auth';

export function SignInButton() {
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  
  const handleSignIn = async () => {
    setLoading(true);
    setError(null);
    
    try {
      const auth = getAuth();
      const provider = new GoogleAuthProvider();
      
      // Sign in with Firebase
      const result = await signInWithPopup(auth, provider);
      const idToken = await result.user.getIdToken();
      
      // Get guest ID if exists
      const guestId = localStorage.getItem('guestId');
      
      // Merge guest account
      if (guestId) {
        const response = await fetch('/auth/merge-guest', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
            'Authorization': `Bearer ${idToken}`
          },
          body: JSON.stringify({ guest_id: guestId })
        });
        
        if (response.ok) {
          console.log('Guest account merged successfully');
          localStorage.removeItem('guestId');
        }
      }
      
      // Store token
      localStorage.setItem('firebaseToken', idToken);
      
      // Reload or redirect
      window.location.reload();
      
    } catch (err) {
      setError(err.message);
      console.error('Sign in error:', err);
    } finally {
      setLoading(false);
    }
  };
  
  return (
    <div>
      <button onClick={handleSignIn} disabled={loading}>
        {loading ? 'Signing in...' : 'Sign in with Google'}
      </button>
      {error && <p className="error">{error}</p>}
    </div>
  );
}
```

---

## Error Handling

### Common Error Responses

#### 401 Unauthorized

```json
{
  "detail": "Authentication failed. Provide Bearer token or X-Guest-ID."
}
```

**Cause:** No authentication provided  
**Fix:** Include either `Authorization` header or `X-Guest-ID` header

---

#### 401 Token Expired

```json
{
  "detail": "Firebase token has expired. Please sign in again."
}
```

**Cause:** Firebase token is older than 1 hour  
**Fix:** Refresh the token or re-authenticate

```javascript
// Force token refresh
const user = auth.currentUser;
const newToken = await user.getIdToken(true); // Force refresh
localStorage.setItem('firebaseToken', newToken);
```

---

#### 403 Forbidden

```json
{
  "detail": "Guest limit reached. Please log in to continue."
}
```

**Cause:** Guest user hit conversation limit  
**Fix:** Show sign-in modal

```javascript
if (error.status === 403 && error.detail.includes('Guest limit')) {
  showSignInModal({
    message: 'You\'ve reached the guest limit. Sign in to continue!',
    onSignIn: handleSignIn
  });
}
```

---

#### 403 Invalid Guest Access

```json
{
  "detail": "Invalid guest access to authenticated account"
}
```

**Cause:** Guest ID belongs to an authenticated user  
**Fix:** Clear guest ID and force re-authentication

```javascript
localStorage.removeItem('guestId');
// Redirect to sign in
```

---

#### 403 Cannot Merge

```json
{
  "detail": "Cannot merge authenticated accounts"
}
```

**Cause:** Trying to merge two authenticated accounts  
**Fix:** This shouldn't happen in normal flow. Log error and continue.

---

### Error Handling Pattern

```javascript
async function makeApiRequest(endpoint, options) {
  try {
    const response = await fetch(endpoint, options);
    
    if (!response.ok) {
      const error = await response.json();
      
      // Handle specific errors
      switch (response.status) {
        case 401:
          if (error.detail.includes('expired')) {
            await refreshToken();
            return makeApiRequest(endpoint, options); // Retry
          }
          // Redirect to login
          redirectToLogin();
          break;
          
        case 403:
          if (error.detail.includes('Guest limit')) {
            showSignInPrompt();
          } else if (error.detail.includes('Invalid guest access')) {
            localStorage.removeItem('guestId');
            redirectToLogin();
          }
          break;
          
        case 500:
          showErrorMessage('Server error. Please try again.');
          break;
          
        default:
          showErrorMessage(error.detail);
      }
      
      throw new Error(error.detail);
    }
    
    return response.json();
    
  } catch (error) {
    console.error('API request failed:', error);
    throw error;
  }
}
```

---

## Best Practices

### 1. **Always Store Guest ID**

```javascript
// ✅ Good - Generate once and persist
const guestId = localStorage.getItem('guestId') || crypto.randomUUID();
localStorage.setItem('guestId', guestId);

// ❌ Bad - Generate new ID each time
const guestId = crypto.randomUUID(); // User loses data on refresh!
```

### 2. **Clean Up After Merge**

```javascript
// ✅ Good - Remove guest ID after successful merge
await mergeGuestAccount(guestId);
localStorage.removeItem('guestId');

// ❌ Bad - Keep stale guest ID
await mergeGuestAccount(guestId);
// Guest ID still in storage, might cause issues
```

### 3. **Handle Token Refresh Proactively**

```javascript
// ✅ Good - Refresh before expiry
setInterval(async () => {
  const user = auth.currentUser;
  if (user) {
    const token = await user.getIdToken(true);
    localStorage.setItem('firebaseToken', token);
  }
}, 50 * 60 * 1000); // Refresh every 50 minutes

// ❌ Bad - Wait for 401 error
// Only refresh when token expires and request fails
```

### 4. **Show Guest Limits Proactively**

```javascript
// ✅ Good - Show limit before hitting it
const conversationCount = conversations.length;
if (isGuest && conversationCount >= 2) {
  showBanner('You have 1 conversation left. Sign in for unlimited access!');
}

// ❌ Bad - Only show error after limit hit
// User creates 4th conversation → 403 error → frustrated
```

### 5. **Graceful Degradation**

```javascript
// ✅ Good - Fall back gracefully
try {
  await mergeGuestAccount(guestId);
  localStorage.removeItem('guestId');
} catch (error) {
  console.error('Merge failed, but user is still authenticated');
  // User can still use the app, just without guest data
}

// ❌ Bad - Block user if merge fails
try {
  await mergeGuestAccount(guestId);
} catch (error) {
  showError('Sign in failed!');
  signOut(); // User loses access!
}
```

### 6. **Use Axios Interceptors (Optional)**

```javascript
import axios from 'axios';

const api = axios.create({
  baseURL: 'https://your-api.com'
});

// Request interceptor - Add auth headers
api.interceptors.request.use(async (config) => {
  const token = localStorage.getItem('firebaseToken');
  const guestId = localStorage.getItem('guestId');
  
  if (token) {
    config.headers.Authorization = `Bearer ${token}`;
  } else if (guestId) {
    config.headers['X-Guest-ID'] = guestId;
  }
  
  return config;
});

// Response interceptor - Handle errors
api.interceptors.response.use(
  response => response,
  async (error) => {
    if (error.response?.status === 401) {
      if (error.response.data?.detail?.includes('expired')) {
        // Refresh token and retry
        const user = auth.currentUser;
        const newToken = await user.getIdToken(true);
        localStorage.setItem('firebaseToken', newToken);
        
        error.config.headers.Authorization = `Bearer ${newToken}`;
        return api.request(error.config);
      }
    }
    return Promise.reject(error);
  }
);
```

---

## Testing Checklist

### Guest Flow
- [ ] Guest ID is generated and stored on first visit
- [ ] Guest ID persists across page refreshes
- [ ] Guest can create up to 3 conversations
- [ ] 4th conversation shows error and sign-in prompt
- [ ] Guest data is visible in API responses

### Authentication Flow
- [ ] Sign in with Google works
- [ ] Firebase token is stored after sign-in
- [ ] Token is included in API requests
- [ ] Token refresh works after expiry
- [ ] Sign out clears token

### Merge Flow
- [ ] Guest data merges successfully on sign-in
- [ ] Guest ID is removed after merge
- [ ] Conversations appear in authenticated account
- [ ] Tags are merged without duplicates
- [ ] Memories are transferred correctly
- [ ] Multiple merge attempts don't cause errors

### Error Handling
- [ ] Expired token triggers refresh
- [ ] Missing auth shows appropriate error
- [ ] Guest limit shows sign-in prompt
- [ ] Network errors are handled gracefully
- [ ] Invalid guest access clears guest ID

---

## Support

For questions or issues:
- **Backend Repo:** [GitHub Repository Link]
- **API Documentation:** `https://your-api.com/docs`
- **Slack:** #frontend-support
- **Email:** dev-support@example.com

---

## Changelog

**v1.0 - February 9, 2026**
- Initial authentication system
- Guest user support
- Firebase integration
- Account merging
- Security fixes applied
