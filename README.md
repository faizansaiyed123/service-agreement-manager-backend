# Service Agreement Manager Backend

Backend API for HVAC, plumbing, and related-trade service businesses.

## Status

Initial repository bootstrap. Implementation status is tracked in `docs/PROGRESS.md`; do not treat planned features as implemented.

## Intended stack

- Python 3.12, FastAPI, Pydantic v2
- SQLAlchemy 2.x, PostgreSQL, Alembic
- pytest, HTTPX, Ruff, mypy
- Docker Compose for local development

## Local development

Copy `.env.example` to `.env`, then start the stack:

```sh
cp .env.example .env
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api pytest
```

API docs: http://localhost:8000/docs  
Liveness: http://localhost:8000/health/live  
Readiness: http://localhost:8000/health/ready

Never use development secrets in production. See `docs/PROJECT_CONTEXT.md` and `docs/RECOVERY.md`.
