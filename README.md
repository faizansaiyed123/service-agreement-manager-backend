# Service Agreement Manager Backend

Backend API for HVAC, plumbing and related-trade service businesses.

## Stack
- Python 3.12, FastAPI and Pydantic v2
- SQLAlchemy 2.x, PostgreSQL and Alembic
- Pytest, HTTPX, Ruff and GitHub Actions
- Docker Compose for local development

## Local development
Copy `.env.example` to `.env`, then start the stack:

```sh
docker compose up --build -d
docker compose exec api alembic upgrade head
docker compose exec api pytest
```

OpenAPI / Swagger: http://localhost:8000/docs  
Liveness: http://localhost:8000/health/live  
Readiness: http://localhost:8000/health/ready

## API modules
- Authentication and session lifecycle: `/api/v1/auth`
- Organization profile: `/api/v1/companies/current`
- Customers, contacts and service locations: `/api/v1/customers`
- Equipment: `/api/v1/equipment`
- Service catalog: `/api/v1/service-catalog`
- Agreement lifecycle, versions and events: `/api/v1/agreements`

Agreement API supports drafts, proposal snapshots, acceptance evidence, delayed activation, suspension/resumption, cancellation, version history and event history. The implementation is ongoing: check `docs/PROGRESS.md` and GitHub Actions before relying on production readiness.

Never use development secrets in production. Copy placeholders only and replace them with secure values.
