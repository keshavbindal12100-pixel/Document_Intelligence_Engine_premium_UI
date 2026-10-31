# Workflow Automation & Document Intelligence Engine (Backend)

A production-grade, asynchronous backend architecture for intelligent document processing, OCR extraction, confidence scoring, human-in-the-loop review, and workflow automation.

---

## Architecture Overview

- **Framework**: FastAPI (Async Python 3.12+)
- **Database & ORM**: PostgreSQL 16 + SQLAlchemy 2.x (Async with `asyncpg`)
- **Migrations**: Alembic
- **Validation**: Pydantic v2 & `pydantic-settings`
- **Task Queue**: Celery + Redis Broker
- **Security**: JWT (HS256) + Argon2/Bcrypt + Workspace-level RBAC
- **Testing**: pytest + pytest-asyncio + httpx + pytest-cov

---

## Directory Structure

```
backend/
├── app/
│   ├── main.py                  # FastAPI entry point & middleware
│   ├── core/                    # Security, Config, Permissions, Exceptions, Logging
│   ├── db/                      # Database engine, base models, Alembic migrations
│   ├── models/                  # SQLAlchemy 2.x declarative domain models
│   ├── schemas/                 # Pydantic v2 DTO and validation models
│   ├── api/                     # REST API version 1 routers and dependencies
│   ├── services/                # Business logic and domain service layers
│   ├── repositories/            # Async data persistence layer with multi-tenancy
│   ├── workers/                 # Celery app and asynchronous background tasks
│   └── utils/                   # File validation and utility helpers
├── tests/                       # Unit, integration, and API test suite
├── alembic.ini                  # Alembic database migration config
├── Dockerfile                   # Multi-stage production container build
├── docker-compose.yml           # Multi-container orchestration (API, Worker, DB, Redis)
├── requirements.txt             # Core backend dependencies
├── .env.example                 # Environment configuration template
└── README.md
```

---

## Security & Multi-Tenancy Design

1. **Workspace Isolation**:
   - Every primary entity (`Document`, `ExtractedField`, `DocumentTemplate`, `Workflow`, `WorkflowExecution`, `Integration`, `AuditLog`) is strictly tied to a `workspace_id`.
   - Repositories automatically enforce workspace boundaries, preventing cross-tenant data leaks.

2. **Role-Based Access Control (RBAC)**:
   - **`ADMIN`**: Full permissions (user & member management, settings, deletions).
   - **`EDITOR`**: Upload documents, manage templates & workflows, execute extractions.
   - **`REVIEWER`**: View documents, correct fields, approve/reject human review decisions.
   - **`VIEWER`**: Read-only access across the workspace.

3. **File Handling & Storage Security**:
   - File extensions and MIME content types validated before storage.
   - SHA-256 duplicate fingerprinting.
   - Size limit controls (default 25 MB max).
   - Local filesystem workspace partitioning.

---

## Quickstart & Local Setup

### 1. Prerequisites
- Python 3.12+
- Docker & Docker Compose (optional for local DB/Redis)

### 2. Environment Setup
```bash
# Clone and navigate to backend
cd backend

# Create and activate virtual environment
python -m venv .venv
# On Windows:
.\.venv\Scripts\activate
# On Linux/macOS:
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Copy environment file
cp .env.example .env
```

### 3. Database Migrations
```bash
alembic upgrade head
```

### 4. Running the Application
```bash
# Start API server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

# Start Celery Worker (in a separate terminal)
celery -A app.workers.celery_app.celery_app worker --loglevel=info
```

### 5. Running with Docker Compose
```bash
docker compose up -d --build
```

---

## Running the Test Suite

```bash
# Run all tests (Unit, Integration, API)
pytest

# Run tests with coverage report
pytest --cov=app --cov-report=term-missing

# Run Ruff linter and formatter
ruff check .
ruff format --check .
```

