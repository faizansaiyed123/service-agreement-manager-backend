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
docker compose exec api ruff check .
```

OpenAPI / Swagger: http://localhost:8000/docs  
Liveness: http://localhost:8000/health/live  
Readiness: http://localhost:8000/health/ready

## API modules
- Authentication and sessions: `/api/v1/auth`
- Company profile and users: `/api/v1/companies/current`, `/api/v1/users`
- Customers, contacts and service locations: `/api/v1/customers`
- Equipment and catalog: `/api/v1/equipment`, `/api/v1/service-catalog`
- Agreements and renewal offers: `/api/v1/agreements`
- Maintenance schedules and work orders: `/api/v1/maintenance/schedules`, `/api/v1/work-orders`
- Invoices and payments: `/api/v1/invoices`
- Notification outbox: `/api/v1/notifications`
- Operational reports: `/api/v1/reports`
- CSV exports: `/api/v1/exports/customers.csv`, `invoices.csv`, `work-orders.csv`, `agreements.csv`

The notification worker can be run with `python -m app.workers.notifications` in an environment where SMTP settings are configured. SMTP delivery has not been verified without an actual provider. No automatic recurring invoices are generated until agreement total-vs-installment pricing is explicitly defined.

## Verification
GitHub Actions runs Ruff and Pytest and applies all Alembic migrations against a PostgreSQL 16 service. API tests currently use SQLite for speed; the migration step itself runs against PostgreSQL. Local setup success and production readiness should be verified in the target environment.

Never use development secrets in production.
