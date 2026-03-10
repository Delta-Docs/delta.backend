# delta.backend


## Table of Contents
- [Overview](#overview)
- [Getting Started](#getting-started)
- [Architecture](#architecture)
   - [The Web Dashboard](#the-web-dashboard)
   - [The GitHub App](#the-github-app)
   - [GitHub Webhook Events](#github-webhook-events)
   - [Redis Queue and RQ Workers](#redis-queue-and-rq-workers)
   - [LangGraph Workflow](#langgraph-workflow)
- [Project Structure](#project-structure)
- [Testing](#testing)
- [Contributing](#contributing)
- [LICENSE](#license)
- [Team](#team)


> **More documentation available at [/docs](/docs). See:**
> - [API Documentation](docs/API_DOCUMENTATON.md)
> - [Auth Documentation](docs/AUTH_DOCUMENTATION.md)
> - [Database Documentation](docs/DB_DOCUMENTATION.md)

## Overview

Delta is a continuous documentation platform that treats documentation as a living part of your codebase, automatically detecting and preventing drift. By integrating directly with your CI/CD pipeline, it analyses every Pull Request to ensure documentation, whether it be API references, setup guides, etc. remain perfectly synchronised with your evolving code - effectively linting your documentation.


## Getting Started

### Prerequisites

- Python 3.10+
- Docker
- Git
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
   POSTGRES_CONNECTION_URL="postgresql://postgres:1234@localhost/postgres"

   # Auth
   SECRET_KEY="YOUR_SECRET_KEY"
   ALGORITHM="ALGORITHM_USED"
   ACCESS_TOKEN_EXPIRE_MINUTES=60
   REFRESH_TOKEN_EXPIRE_DAYS=15

   # GitHub App
   GITHUB_APP_ID="YOUR_GITHUB_APP_ID"
   GITHUB_PRIVATE_KEY_PATH="path/to/private-key.pem"
   GITHUB_CLIENT_ID="YOUR_GITHUB_CLIENT_ID"
   GITHUB_CLIENT_SECRET="YOUR_GITHUB_CLIENT_SECRET"
   GITHUB_WEBHOOK_SECRET="YOUR_GITHUB_WEBHOOK_SECRET"

   # RQ Config
   REDIS_URL="redis://localhost:6379/0"
   NUM_WORKERS=2

   FRONTEND_URL="http://localhost:5173"

   REPOS_BASE_PATH="/path/to/delta.backend/repos"

   # LLM Config
   GEMINI_API_KEY="YOUR_GEMINI_API_KEY"
   LLM_MODEL="gemini-2.5-flash"
   ```

4. **Run setup command**
   ```bash
   make setup
   ```
   This will:
   - Create a Python Virtual Environment (at `.venv`)
   - Install all `pip` dependencies
   - Start Docker containers
   - Run database migrations

5. **Start development server**
   ```bash
   make dev
   ```

   The API will be available at: `http://localhost:8000`

### Quick Commands

```bash
# Install pip dependencies only
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

# Clean cache files
make clean

# Run ruff and pyrefly linting
make lint

# Run ruff's formatter
make format

# Run all python tests
make test
```

> **NOTE**: The `make` commands are designed to work only on Linux.  
> If you are using another OS, please check the Makefile and execute the corresponding commands directly.



## Architecture

![Delta Architecture](/images/Delta_Architecture_Diagram.png)

### The Web Dashboard 

It allows the user to interact and set up Delta. It is a React + Vite application that allows the user to:
 - Sign Up and access Delta
 - Link new repositories
 - Manage settings for linked repositories (file_ignore_patterns, target branch, etc.)
- See details and status of Pull Requests

[See delta.frontend code.](https://github.com/Delta-Docs/delta.frontend)

### The GitHub App
The **heart** of the system. On linking a repository, The **Delta-Docs** GitHub App is automatically installed in the repository. It is responsible for 2 things: 
- Primarily, it sets up webhooks for the linked repository.
- All GitHub API calls that access data from a private GitHub repository, require an access token. These access tokens however expire 8 hours after creation (during initial GitHub OAuth). This means we need to renew the access token. Hence, we use the GitHub App's private key to sign a JWT and get a valid access token.

### GitHub Webhook Events
Delta completely relies on GitHub webhook events to operate. Currently, it is set up to track 4 kinds of webhook events:
- `installation`: It is received when the user performs some action related to the installation of the GitHub App. It is triggered with the installation (which also includes the linking of at least 1 repository), uninstallation, suspension or unsuspension of the GitHub App.
- `installation_repository`: It is received when a repository is added or removed from an existing installation.
- `pull_request`: We handle two types of actions - `opened` for when a new pull request is raised in any of the linked repositories and `synchronize` for when new commits are pushed to an already existing PR.
- `check_suite`: We handle only the `rerequested` action which we receive when the `Re-Run all checks` button is clicked in the PR.

`github_webhook/router.py` routes the webhook event payload to its appropriate handler which updates the DB and starts workflows accordingly.

### Redis Queue and RQ Workers
Upon receiving a `pull_request` webhook event, a record in the `DriftEvent` table is created. Every PR raised has to be analysed. Due to the amount of time processing a PR may take and considering the timeout limits of REST APIs, this analysis and workflow has to be done asynchronously. 

This is the reason we use Redis Queue. It is a simple queue implemented with Redis that has multiple consumers (the RQ Worker Pool). It is simple and complex enough for its purpose here at Delta.

When a `DriftEvent` record is created, its ID is enqueued for processing. Any free RQ worker from the worker pool picks up the id and executes the task assigned with it.

Whenever a drift event analysis job has to be re-run, its state in the DB is cleared and it is re-enqueued into RQ for a free worker to pick it up.

### LangGraph Workflow
Once an RQ worker picks up a drift event, it runs the 7 node LangGraph pipeline. We originally thought of implementing a more complex graph structure, but as it evolved, we settled on a linear pipeline. While LangChain would have been sufficient, LangGraph gives us the flexibility for future upgrades, if any.

The pipeline is split into two phases. The first phase analyses the PR for drift. If drift is detected, the second phase is also run to generate documentation updates.

**Phase 1: Drift Analysis**

- **Scout Changes:** It extracts code changes from the PR by analysing git diffs and uses Python's AST parser to identify modified functions, classes, and API routes.
- **Retrieve Docs:** It recursively loads all `.md` files from the repo's docs directory. For each code change detected in the previous node, it does keyword based searches to find relevant documentation sections.
- **Deep Analyze:** This is where the LLM comes in. For each code change, it compares the git diff with the relevant documentation snippets. The LLM performs semantic analysis to check if the documentation is up to date with the code changes.
- **Aggregate Results:** It aggregates all the findings from the previous nodes, calculates an overall drift score, and updates the  GitHub Check Run. 

If drift is detected in Phase 1, the workflow conditionally proceeds to the second phase. Otherwise, it ends here.

**Phase 2: Documentation Generation**

- **Plan Updates:** It analyses all the drift findings and creates a documentation update strategy, that specifies exactly which files need changes and what sections to update. It also creates a new branch off the original PR branch where the documentation fixes will be committed.
- **Rewrite Docs:** The LLM generates updated documentation content for each target file. It keeps in mind the repo's configured `style_preference` (like professional, casual, etc.) and follows any custom `docs_policies` that were set. The generated content is written to the documentation files in the cloned repository.
- **Apply Changes:** It commits all the documentation changes to the `docs/delta-fix` branch, pushes them to GitHub, and raises a Pull Request with the updated documentation. It also requests review from the configured reviewer.


## Project Structure

```
delta.backend/
   ├── alembic/                             # Database migrations
   │   ├── versions/                        # Migration files
   │   ├── env.py                           # Alembic environment config
   │   └── script.py.mako                   # Migration template
   │
   ├── app/                                 # Main application code
   │   ├── agents/                          # LangGraph multi-agent workflow
   │   │   ├── nodes/                       # Agent nodes
   │   │   ├── graph.py                     # LangGraph workflow graph
   │   │   ├── llm.py                       # LLM configuration
   │   │   ├── policy_guard.py              # Policy validation
   │   │   ├── prompts.py                   # Agent prompts
   │   │   └── state.py                     # Workflow state definitions
   │   │
   │   ├── core/                            # Core functionality
   │   │         
   │   ├── db/                              # Database configuration
   │   │   ├── base.py                      # Import all models
   │   │   ├── base_class.py                # SQLAlchemy declarative base
   │   │   └── session.py                   # Database session factory
   │   │         
   │   ├── models/                          # SQLAlchemy models (Schema)
   │   ├── routers/                         # API route handlers
   │   ├── schemas/                         # Pydantic schemas
   │   ├── services/                        # Business logic
   │   │         
   │   ├── api.py                           # API router aggregation
   │   ├── deps.py                          # Dependency injection
   │   └── main.py                          # FastAPI application entry point
   │
   ├── bruno/                               # API testing (Bruno client)
   │   ├── auth/                            # Auth request collection
   │   ├── dashboard/                       # Dashboard request collection
   │   ├── environments/                    # Bruno environments
   │   ├── notifications/                   # Notification request collection
   │   └── repos/                           # Repos request collection
   │
   ├── docs/                                # Markdown files for documentation
   ├── images/                              # Diagrams for Delta documentation
   ├── tests/                               # Unit & Integration tests
   │         
   ├── .env.example                         # Sample .env file
   ├── .gitignore                           # Git ignore rules
   ├── alembic.ini                          # Alembic configuration
   ├── docker-compose.yml                   # Docker services definition
   ├── Dockerfile                           # Docker image definition
   ├── LICENSE                              # MIT License
   ├── Makefile                             # Development commands
   ├── pyrefly.toml                         # Pyrefly configuration
   ├── pytest.ini                           # Pytest configuration
   ├── README.md                            # Project documentation
   ├── requirements.txt                     # Python dependencies
   ├── ruff.toml                            # Ruff configuration
   └── workers.py                           # Script to run the RQ workers
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


## Contributing

Please follow the existing code style and conventions. We follow [Conventional Commits](https://www.conventionalcommits.org/) for our commit messages.

Before submitting a Pull Request, please run the following commands:

```bash
# Check for linting and type errors
ruff check .
pyrefly check .

# Format code
ruff format .
```


## LICENSE

This project is licensed under the [MIT LICENSE](LICENSE).


## Team

The people working to make ▲ a possibility:

| Name                   | Roll Number      | GitHub ID                                                   |
|------------------------|------------------|-------------------------------------------------------------|
| A Jahnavi              | CB.SC.U4CSE23503 | [jahnavialladasetti](https://github.com/jahnavialladasetti) |
| Adithya Menon R        | CB.SC.U4CSE23506 | [adithya-menon-r](https://github.com/adithya-menon-r)       |
| Dheeraj KB             | CB.SC.U4CSE23510 | [Dheeraj-74](https://github.com/Dheeraj-74)                 |
| Midhunan V Prabhaharan | CB.SC.U4CSE23532 | [midhunann](https://github.com/midhunann)                   |
| Yogini Aishwaryaa      | CB.SC.U4CSE23557 | [yoginiaishwaryaa](https://github.com/yoginiaishwaryaa)     |
