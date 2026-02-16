# API Endpoints

## Base URL
- **Development**: `http://localhost:8000/api`
- **Production**: `https://production-domain.com/api`

## Authentication Endpoints (`/api/auth`)

### POST `/auth/signup`
Create a new user account.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword_hash",
  "full_name": "John Doe"
}
```

**Response:**
```json
{
  "message": "User created successfully"
}
```

### POST `/auth/login`
Login with email and password.

**Request Body:**
```json
{
  "email": "user@example.com",
  "password": "securepassword_hash"
}
```

**Response:**
- Sets `access_token` and `refresh_token` cookies
```json
{
  "email": "user@example.com",
  "name": "User Name"
}
```

### POST `/auth/logout`
Logout and invalidate tokens.

**Response:**
- Deletes `access_token` and `refresh_token` cookies
```json
{
  "message": "Logout successfully"
}
```

### GET `/auth/github/callback`
GitHub OAuth callback handler.

**Query Params:**
- `code`: Authorization code from GitHub


## Webhook Endpoints (`/api/webhook`)

### POST `/webhook/github`
Receives GitHub webhook events.

**Headers:**
- `X-GitHub-Event`: Event Type (e.g., `pull_request`, `push`)
- `X-Hub-Signature-256`: HMAC signature for verification

**Request Body:**
GitHub Webhook Payload 

**Response:**
```json
{
  "status": "Received and Processed Event"
}
```

## Repository Endpoints (`/api/repos`)

### GET `/repos`
List all repositories for the authenticated user.

**Response:**
```json
[
  {
    "id": "13b1034a-d60b-4747-a87e-2b696da261db",
    "repo_name": "owner/repo_name",
    "is_active": true,
    "is_suspended": false,
    "avatar_url": "repo avatar url",
    "docs_root_path": "/docs",
    "target_branch": "main",
    "drift_sensitivity": 0.5,
    "style_preference": "professional",
    "file_ignore_patterns": null,
    "last_synced_at": null,
  }
]
```

### PUT `/repos/{repo_id}/activate`
Activate or deactivate drift monitoring for a repository.

**Request Body:**
```json
{
  "is_active": false
}
```

**Response:**
```json
{
  "id": "13b1034a-d60b-4747-a87e-2b696da261db",
  "repo_name": "owner/repo_name",
  "is_active": false,
  "is_suspended": false,
  "avatar_url": "repo avatar url",
  "docs_root_path": "/docs",
  "target_branch": "main",
  "drift_sensitivity": 0.5,
  "style_preference": "professional",
  "file_ignore_patterns": null,
  "last_synced_at": null,
}
```

### PUT `/repos/{repo_id}/settings`
Update repository configuration.

**Request Body:**
```json
{
  "docs_root_path": "/docs",
  "target_branch": "main",
  "drift_sensitivity": 0.7,
  "style_preference": "technical",
  "file_ignore_patterns": ["*.test.js", "*.spec.ts"]
}
```

**Response:**
```json
{
  "id": "13b1034a-d60b-4747-a87e-2b696da261db",
  "repo_name": "owner/repo_name",
  "is_active": true,
  "is_suspended": false,
  "avatar_url": "repo avatar url",
  "docs_root_path": "/docs",
  "target_branch": "main",
  "drift_sensitivity": 0.7,
  "style_preference": "technical",
  "file_ignore_patterns": ["*.test.js", "*.spec.ts"],
  "last_synced_at": null,
}
```

## Dashboard Endpoints (`/api/dashboard`)

### GET `/dashboard/stats`
Get dashboard statistics for the authenticated user.

**Response:**
```json
{
  "installations_count": 2,
  "repos_linked_count": 10,
  "drift_events_count": 32,
  "pr_waiting_count": 4
}
```

### GET `/dashboard/repos`
Get basic repository information for the 5 most recently linked repositories:

**Response:**
```json
[
  {
    "name": "repo name",
    "description": "repo description",
    "language": "Python",
    "stargazers_count": 2,
    "forks_count": 5,
    "avatar_url": "Avatar URL"
  }
]
```
