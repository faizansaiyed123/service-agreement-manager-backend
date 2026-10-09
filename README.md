# Service Agreement Manager Backend

Backend API for HVAC, plumbing, and related-trade service businesses.

## Current status

The first committed slice implements FastAPI infrastructure, company onboarding, authentication/session rotation, company-profile settings, customers, contacts, and service locations. Remaining business modules are tracked in docs/ROADMAP.md; do not treat planned features as complete.

## Stack

- Python 3.12, FastAPI, Pydantic v2
- SQLAlchemy 2.x, PostgreSQL, Alembic
- pytest, HTTPX, Ruff
- Docker Compose and GitHub Actions

## Local development

Copy .env.example to .env and replace the development JWT secret. Then run:

    docker compose up --build -d
    docker compose exec api alembic current
    docker compose exec api pytest
    docker compose exec api ruff check .

Swagger UI: http://localhost:8000/docs  
Liveness: http://localhost:8000/health/live  
Readiness: http://localhost:8000/health/ready

Never use development credentials in production. Read docs/PROJECT_CONTEXT.md and docs/RECOVERY.md.
