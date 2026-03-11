# Project Delta: DevOps & Infrastructure Engineering

A comprehensive technical overview of the DevOps lifecycle, architectural components, and automation pipelines implemented in Project Delta.

---

## 1. System Architecture & Orchestration

Project Delta is built on a microservices-oriented architecture, fully containerized using **Docker**. This ensures a consistent runtime environment across all development and production stages.

### Infrastructure Overview (Docker Compose)

The entire backend stack is defined and managed via `docker-compose.yml`. This configuration handles service isolation, networking, and volume persistence.

#### `docker-compose.yml` Configuration:
```yaml
services:
  postgres:
    image: postgres:18-alpine
    container_name: delta-postgres
    restart: on-failure
    environment:
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: 1234
      POSTGRES_DB: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    container_name: delta-redis
    restart: on-failure
    ports:
      - "6379:6379"
    volumes:
      - redis_data:/data
    command: redis-server --appendonly yes

  drizzle-gateway:
    image: ghcr.io/drizzle-team/gateway:latest
    container_name: delta-drizzle-gateway
    environment:
      DATABASE_URL: postgresql://postgres:1234@postgres:5432/postgres
      STORE_PATH: /app
    restart: on-failure
    depends_on:
      - postgres
    ports:
      - "4983:4983"
    volumes:
      - drizzle_gateway_data:/app

  api:
    build: .
    container_name: delta-api
    restart: always
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
    env_file:
      - .env
    volumes:
      - repos_data:/repos

  worker:
    build: .
    container_name: delta-worker
    restart: always
    command: python workers.py
    depends_on:
      - redis
      - postgres
    env_file:
      - .env
    volumes:
      - repos_data:/repos

volumes:
  postgres_data:
  redis_data:
  drizzle_gateway_data:
  repos_data:
```

### Service Breakdown:
1.  **API (FastAPI)**: The primary application server handling HTTP traffic. It relies on `postgres` for data and `redis` for caching.
2.  **Worker**: A Celery/standalone background processor that executes long-running tasks asynchronously.
3.  **PostgreSQL**: A relational database for persistent storage, using the `18-alpine` image for a minimal footprint.
4.  **Redis**: Handles message brokering and session management with `appendonly` persistence enabled.

---

## 2. CI/CD Lifecycle (GitHub Actions)

CI/CD pipeline ensures that every code change is validated before reaching production. This automated feedback loop is critical in a collaborative environment to prevent regressions and maintain high code quality standards.

### Continuous Integration (`backend-ci.yml`)

The CI pipeline runs on every `push` and `pull_request` to the `main` branch. Its goal is to catch bugs, security vulnerabilities, and formatting issues early in the development cycle. By automating these checks, we ensure that the `main` branch always remains in a deployable state.

```yaml
name: Backend CI

on:
  push:
    branches: [ "main" ]
  pull_request:
    branches: [ "main" ]

jobs:
  ruff-lint:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python 3.12
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install ruff
      run: pip install ruff
    - name: Run ruff check
      run: ruff check

  pyrefly-typecheck:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4
    - name: Set up Python 3.12
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
    - name: Install pyrefly
      run: pip install pyrefly
    - name: Run pyrefly
      run: pyrefly check

  backend-tests:
    runs-on: ubuntu-latest

    steps:
    - uses: actions/checkout@v4
    - name: Set up Python 3.12
      uses: actions/setup-python@v5
      with:
        python-version: "3.12"
        cache: 'pip'

    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt

    - name: Set up environment
      run: cp .env.example .env

    - name: Run tests
      run: python -m pytest
```

---

### GitHub Repository Secrets

For security and privacy, sensitive data such as server IP addresses, login credentials, and private SSH keys are neve stored in the codebase. Instead, they are managed via **GitHub Repository Secrets**.

These secrets are encrypted environment variables that GitHub Actions can access during runtime but are hidden from all users, including repository contributors.

**Key Secrets Configured:**
- `VPS_IP`: The public IP address of the production server.
- `VPS_USERNAME`: The administrative user authorized to perform deployments.
- `VPS_SSH_KEY`: The private RSA/ED25519 key used for secure, passwordless SSH authentication.

---

### Continuous Deployment (`deploy.yml`)

Once the CI pipeline passes, the CD pipeline automates the rollout to our production VPS.

```yaml
name: Deploy to VPS
on:
  push:
    branches: [ "main" ]
jobs:
  deploy:
    runs-on: ubuntu-latest
    steps:
    - uses: actions/checkout@v4

    - name: Deploy via SSH
      uses: appleboy/ssh-action@v1.0.3
      with:
        host: ${{ secrets.VPS_IP }}
        username: ${{ secrets.VPS_USERNAME }}
        key: ${{ secrets.VPS_SSH_KEY }}
        script: |
          # 1. Enter the project folder
          cd delta.backend

          # 2. Pull the latest code 
          git pull origin main

          # 3. Build and run updated containers
          sudo docker-compose up --build -d

          # 4. Migrate the DB
          sudo docker-compose exec -T api alembic upgrade head
```

#### Deployment Mechanisms:
- **Git Hook**: Pulls the latest delta from the repository.
- **Docker-Compose Logic**: The `--build -d` flags ensure that any changes to the `Dockerfile` or source code are rebuilt into new images and restarted without downtime.

---

## 3. Operational Infrastructure

### Frontend (Vercel)
The React/TypeScript application is hosted on **Vercel**.
- **Edge Deployment**: Static assets are distributed globally.
- **Vercel Rewrites**: Configured in `vercel.json` to route all traffic to `index.html`, enabling client-side navigation.

### Backend (VPS)
Hosted on a dedicated **Ubuntu/Linux VPS**.
- **Orchestration**: Docker Compose manages container life-cycles.
- **Security**: SSH Key authentication is required for all deployment triggers.

---

## 4. Engineering Maintenance

### Configuration Management
All sensitive credentials must be stored in a `.env` file. Do NOT commit the `.env` file to version control.
```bash
# Apply migrations after a schema change
docker-compose exec api alembic upgrade head
```

### Health & Monitoring
```bash
# View live logs for specific service
docker-compose logs -f api
```
