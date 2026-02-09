# delta.backend [WIP]

## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
- [Architecture](#architecture)
- [Project Structure](#project-structure)
- [Database](#database)
- [API Endpoints](#api-endpoints)
- [Authentication](#authentication)
- [Testing](#testing)
- [LICENSE](#license)

## Overview

Delta is a continuous documentation platform that treats documentation as a living part of your codebase, automatically detecting and preventing drift. By integrating directly with your CI/CD pipeline, it analyses every Pull Request to ensure your general documentation, API references, and guides remain perfectly synchronised with your evolving code - effectively linting your documentation.



## Getting Started

### Prerequisites

- Python 3.10+
- Docker
- PostgreSQL 18 (via Docker)
- GitHub App Credentials

### Initial Setup

1. **Clone the repository**
   ```bash
   git clone https://github.com/Delta-Docs/delta.backend.git
   cd delta.backend
   ```

2. **Create a `.env` file**
   ```bash
   cp .env.example .env
   ```

3. **Configure environment variables** (`.env`)
   ```env
   # Database
   POSTGRES_CONNECTION_URL="YOUR_POSTGRES_CONNECTION_URL"
   
   # Auth
   SECRET_KEY="YOUR_SECRET_KEY"
   ALGORITHM="ALGORITHM_USED"

   # GitHub App Credentials
   GITHUB_APP_ID="YOUR_GITHUB_APP_ID"
   GITHUB_PRIVATE_KEY_PATH="keys/PRIVATE_KEY.pem"
   GITHUB_CLIENT_ID="YOUR_GITHUB_CLIENT_ID"
   GITHUB_CLIENT_SECRET="YOUR_GITHUB_CLIENT_SECRET"
   GITHUB_WEBHOOK_SECRET="YOUR_GITHUB_WEBHOOK_SECRET"

   FRONTEND_URL="http://localhost:5173"
   ```

4. **Run setup command**
   ```bash
   make setup
   ```
   This will:
   - Create a Python Virtual Environment (at `.venv`)
   - Install all dependencies
   - Start Docker containers
   - Run database migrations

5. **Start development server**
   ```bash
   make dev
   ```

   The API will be available at: `http://localhost:8000`

### Quick Commands

```bash
# Install dependencies only
make install

# Start Docker services
make docker-up

# Stop Docker services
make docker-down

# Run development server (with reload)
make dev

# Run production server
make run

# Create a new migration
make migrate msg="your migration message"

# Apply migrations
make up

# Rollback all migrations
make down

# Show migration history
make history

# Clean cache files
make clean
```

> **NOTE**: The `make` commands are designed to work only on Linux.  
> If you are using another OS, please check the Makefile and execute the corresponding commands directly.



## Architecture

### A High-Level Architecture

![Delta Architecture](/images/Delta_Architecure_Diagram.png)

### Process Flow  

1. **Raise PR**: Add code and raise a PR in a linked repository
2. **GitHub Event**: Webhook endpoint receives the event
3. **Signature Validation**: HMAC verification using webhook secret
4. **Event Routing**: Routes to appropriate handler based on webhook event type
5. **Drift Analysis**: Compares code changes with documentation changes
6. **Documentation Generartion**: Documentation is updated based on drift findings
7. **Create PR for Updates**: Creates a PR and awaits review for documentation updates



## Project Structure

```
delta.backend/
├── alembic/                             # Database migrations
│   ├── versions/                        # Migration files
│   ├── env.py                           # Alembic environment config
│   └── script.py.mako                   # Migration template
│         
├── app/                                 # Main application code
│   ├── core/                            # Core functionality
│   │   ├── config.py                    # Settings & environment config
│   │   └── security.py                  # Auth & password hashing
│   │         
│   ├── db/                              # Database configuration
│   │   ├── base.py                      # Import all models
│   │   ├── base_class.py                # SQLAlchemy declarative base
│   │   └── session.py                   # Database session factory
│   │         
│   ├── models/                          # SQLAlchemy models (Schema)
│   │         
│   ├── routers/                         # API route handlers
│   │   ├── auth.py                      # Authentication endpoints
│   │   ├── dashboard.py                 # Dashboard Page endpoints
│   │   ├── repos.py                     # Repository Page endpoints
│   │   └── webhooks.py                  # GitHub webhook handler
│   │         
│   ├── schemas/                         # Pydantic schemas
│   │         
│   ├── services/                        # Business logic
│   │   ├── github_api.py                # GitHub API integration
│   │   └── github_webhook_service.py    # Webhook event processing
│   │         
│   ├── api.py                           # API router aggregation
│   ├── deps.py                          # Dependency injection
│   └── main.py                          # FastAPI application entry point
│         
├── bruno/                               # API testing (Bruno client)
│   ├── auth/                            # Auth endpoint tests
│   ├── dashboard/                       # Dashboard tests
│   └── repos/                           # Repository tests
│         
├── keys/                                # GitHub App private keys (gitignored)
│         
├── tests/                               # Unit tests
│   ├── core/                            # Core functionality tests
│   ├── routers/                         # Router tests
│   └── services/                        # Service tests
│         
├── .env                                 # Environment variables (gitignored)
├── alembic.ini                          # Alembic configuration
├── docker-compose.yml                   # Docker services definition
├── Makefile                             # Development commands
├── pytest.ini                           # Pytest configuration
└── requirements.txt                     # Python dependencies
```



## Database

### Schema Diagram

![Delta Schema](/images/Delta_Schema_Diagram.png)

### Database Schema

#### Users Table
```sql
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    full_name VARCHAR,
    email VARCHAR UNIQUE NOT NULL,
    password_hash VARCHAR,
    github_user_id INTEGER UNIQUE,
    github_username VARCHAR,
    current_refresh_token_hash VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now(),
    updated_at TIMESTAMPTZ DEFAULT now()
);
```

#### Installations Table
```sql
CREATE TABLE installations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id BIGINT UNIQUE NOT NULL, 
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    account_name VARCHAR,
    account_type VARCHAR,
    created_at TIMESTAMPTZ DEFAULT now()
);

CREATE INDEX idx_installations_user ON installations(user_id);
```

#### Repositories Table
```sql
CREATE TABLE repositories (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    installation_id BIGINT REFERENCES installations(installation_id) ON DELETE CASCADE,
    repo_name VARCHAR NOT NULL,
    is_active BOOLEAN DEFAULT TRUE,
    is_suspended BOOLEAN DEFAULT FALSE,
    avatar_url VARCHAR,
    docs_root_path VARCHAR DEFAULT './docs',
    target_branch VARCHAR DEFAULT 'main',
    drift_sensitivity FLOAT DEFAULT 0.5,
    style_preference VARCHAR DEFAULT 'professional',
    file_ignore_patterns VARCHAR[],
    last_synced_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(installation_id, repo_name)
);
```

#### Doc Coverage Map Table
```sql
CREATE TABLE doc_coverage_map (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    code_path VARCHAR NOT NULL,
    doc_file_path VARCHAR,
    last_verified_at TIMESTAMPTZ DEFAULT now(),
    UNIQUE(repo_id, code_path, doc_file_path)
);

CREATE INDEX idx_coverage_repo ON doc_coverage_map(repo_id);
```

#### Drift Events Table
```sql
CREATE TABLE drift_events (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    repo_id UUID REFERENCES repositories(id) ON DELETE CASCADE,
    pr_number INTEGER NOT NULL,
    base_sha VARCHAR NOT NULL,
    head_sha VARCHAR NOT NULL,
    check_run_id BIGINT,
    processing_phase VARCHAR DEFAULT 'queued',
    drift_result VARCHAR DEFAULT 'pending',
    overall_drift_score FLOAT,
    summary VARCHAR,
    agent_logs JSONB,
    error_message VARCHAR,
    started_at TIMESTAMPTZ,
    completed_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT check_processing_phase CHECK (processing_phase IN ('queued', 'scouting', 'analyzing', 'generating', 'verifying', 'completed', 'failed')),
    CONSTRAINT check_drift_result CHECK (drift_result IN ('pending', 'clean', 'drift_detected', 'missing_docs', 'error'))
);

CREATE INDEX idx_drift_active_runs ON drift_events (repo_id) 
WHERE processing_phase NOT IN ('completed', 'failed');
```

#### Drift Findings Table
```sql
CREATE TABLE drift_findings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drift_event_id UUID REFERENCES drift_events(id) ON DELETE CASCADE,
    code_path VARCHAR NOT NULL,
    doc_file_path VARCHAR,
    change_type VARCHAR,
    drift_type VARCHAR,
    drift_score FLOAT,
    explanation VARCHAR,
    confidence FLOAT,
    created_at TIMESTAMPTZ DEFAULT now(),
    CONSTRAINT check_finding_change_type CHECK (change_type IN ('added', 'modified', 'deleted')),
    CONSTRAINT check_start_drift_type CHECK (drift_type IN ('outdated_docs', 'missing_docs', 'ambiguous_docs'))
);
```

#### Code Changes Table
```sql
CREATE TABLE code_changes (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    drift_event_id UUID REFERENCES drift_events(id) ON DELETE CASCADE,
    file_path VARCHAR NOT NULL,
    change_type VARCHAR,
    is_code BOOLEAN DEFAULT TRUE,
    CONSTRAINT check_code_change_type CHECK (change_type IN ('added', 'modified', 'deleted'))
);
```

### Database Migrations

Using Alembic for database migrations:

```bash
# Create a new migration
make migrate msg="add new column to users"

# Apply all pending migrations
make up

# Apply one migration
make up-one

# Rollback to base
make down

# Rollback one migration
make down-one

# View migration history
make history
```

> **NOTE**: The `make` commands are designed to work only on Linux.  
> If you are using another OS, please check the Makefile and execute the corresponding commands directly.



## API Endpoints

### Base URL
- **Development**: `http://localhost:8000/api`
- **Production**: `https://production-domain.com/api`

### Authentication Endpoints (`/api/auth`)

#### POST `/auth/signup`
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

#### POST `/auth/login`
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
  "message": "Login successful"
}
```

#### POST `/auth/logout`
Logout and invalidate tokens.

**Response:**
- Deletes `access_token` and `refresh_token` cookies
```json
{
  "message": "Logout successfully"
}
```

#### GET `/auth/github/callback`
GitHub OAuth callback handler.

**Query Params:**
- `code`: Authorization code from GitHub


### Webhook Endpoints (`/api/webhook`)

#### POST `/webhook/github`
Receives GitHub webhook events.

**Headers:**
- `X-GitHub-Event`: Event type (e.g., `pull_request`, `push`)
- `X-Hub-Signature-256`: HMAC signature for verification

**Request Body:**
GitHub webhook payload (varies by event type)

**Response:**
```json
{
  "status": "Received and Processed Event"
}
```

### Repository Endpoints (`/api/repos`)

#### GET `/repos`
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
    "docs_root_path": "./docs",
    "target_branch": "main",
    "drift_sensitivity": 0.5,
    "style_preference": "professional",
    "file_ignore_patterns": null,
    "last_synced_at": null,
  }
]
```

#### PUT `/repos/{repo_id}/activate`
Activate or deactivate drift monitoring for a repository.

**Request Body:**
```json
{
  "is_active": true
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
  "docs_root_path": "./docs",
  "target_branch": "main",
  "drift_sensitivity": 0.5,
  "style_preference": "professional",
  "file_ignore_patterns": null,
  "last_synced_at": null,
}
```

#### PUT `/repos/{repo_id}/settings`
Update repository configuration.

**Request Body:**
```json
{
  "docs_root_path": "./docs",
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
  "docs_root_path": "./docs",
  "target_branch": "main",
  "drift_sensitivity": 0.7,
  "style_preference": "technical",
  "file_ignore_patterns": ["*.test.js", "*.spec.ts"],
  "last_synced_at": null,
}
```

### Dashboard Endpoints (`/api/dashboard`)

#### GET `/dashboard/stats`
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

#### GET `/dashboard/repos`
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



## Authentication

### Authentication Strategy

Delta uses a dual-token authentication system:

1. **Access Token**: Short lived PASETO (1 hour) for API requests
2. **Refresh Token**: Long lived token (7 days) for refreshing access tokens

Both tokens are stored as httponly cookies to prevent XSS attacks.

> **NOTE**: Refreshing of the Access token cookie is handled automatically by the backend when a protected endpoint is accessed.

### Token Structure

**Access Token Payload:**
```json
{
  "sub": "user-uuid",
  "type": "access",
  "exp": 1234567890
}
```

**Refresh Token Payload:**
```json
{
  "sub": "user-uuid",
  "type": "refresh",
  "exp": 1234567890
}
```

### Password Hashing

Passwords are first hashed via SHA-256 into a 64-character hexadecimal string before being re-hashed using Bcrypt with automatic salt generation:

```python
from app.core.security import get_hash, verify_hash

# Hash password
password_hash = get_hash("user_password_hash")

# Verify password
is_valid = verify_hash("user_password_hash", password_hash)
```

> **NOTE**: The password is also hashed in the frontend before it is sent during signup / login to the backend

### Protected Endpoints

Use the `get_current_user` dependency to protect endpoints:

```python
from app.deps import get_current_user
from app.models.user import User

@router.get("/protected")
def protected_endpoint(current_user: User = Depends(get_current_user)):
    # Endpoint code
    ...

```



## Testing

### Running Tests

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run specific test file
pytest tests/test_dashboard.py
```

### Test Structure

```
tests/
├── test_dashboard.py        # Dashboard endpoint tests
├── test_github_api.py       # GitHub API integration tests
├── core/
│   └── test_security.py     # Security utility tests
├── routers/
│   └── test_webhooks.py     # Webhook handler tests
└── services/
    ├── test_github_check_run.py        # Check run tests
    └── test_github_webhook_service.py  # Webhook service tests
```



## LICENSE

This project is licensed under the [MIT LICENSE](LICENSE).
