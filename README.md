# Service Agreement Manager Backend

Backend API for HVAC, plumbing and related-trade service businesses.

## Stack
- Python 3.12, FastAPI and Pydantic v2
- SQLAlchemy 2.x, PostgreSQL and Alembic
- Pytest, HTTPX, Ruff and GitHub Actions
- Docker Compose for local development
- ReportLab for invoice PDFs
- boto3 for S3-compatible attachment storage

## Local development
Copy .env.example to .env, then start the core stack:

    docker compose up --build -d

Run the full test/lint suite locally:

    docker compose exec api pytest
    docker compose exec api ruff check .
    docker compose exec api alembic check

OpenAPI / Swagger: http://localhost:8000/docs
Liveness: http://localhost:8000/health/live
Readiness: http://localhost:8000/health/ready

## API modules
- Authentication, sessions and password recovery: /api/v1/auth
- Company profile and users: /api/v1/companies/current and /api/v1/users
- Branches, local business hours and dated closures: /api/v1/branches
- Customers, contacts, service locations and customer bulk imports: /api/v1/customers and /api/v1/customers/imports
- Equipment and catalog: /api/v1/equipment and /api/v1/service-catalog
- Agreements and renewal offers: /api/v1/agreements
- Maintenance schedules and work orders: /api/v1/maintenance/schedules and /api/v1/work-orders
- Invoices, payments, refunds, credits and PDFs: /api/v1/invoices
- Recurring invoice schedules: /api/v1/recurring-invoices
- Durable email notifications: /api/v1/notifications
- Durable SMS queue: /api/v1/sms
- Webhook endpoints and delivery history: /api/v1/webhooks
- Attachments: /api/v1/attachments
- Operational reports and CSV exports: /api/v1/reports and /api/v1/exports/*.csv

## Workers
Core Compose starts PostgreSQL, API, maintenance worker, billing worker and webhook worker.
Optional profiles are email for SMTP delivery and sms for the HTTP SMS worker.

Example:
    docker compose --profile email --profile sms up --build -d

## Storage
Attachments default to local storage at STORAGE_ROOT. S3-compatible storage can be enabled with STORAGE_BACKEND=s3 or s3-compatible plus the configured bucket and credentials.

## Verification
GitHub Actions applies all Alembic migrations against PostgreSQL 16, runs Ruff, the full pytest suite, dedicated PostgreSQL concurrency tests and Docker Compose smoke checks.

Real SMTP/SMS/S3 provider delivery, production deployment, TLS/proxy setup, secret injection and operational monitoring still require target-environment credentials and infrastructure verification.

## Browser session security

Browser login returns no bearer tokens in JSON. The API sets short-lived access and refresh tokens in `HttpOnly` cookies, validates exact trusted origins on browser requests, and applies CSRF checks to cookie-authenticated state changes. Browser clients must use cookies; bearer tokens remain supported for non-browser API clients. Authentication endpoints have process-local rate limits, which must be supplemented by a provider WAF. Public registration is intentionally disabled in production until email ownership verification exists; use `python -m app.cli create-owner` to bootstrap the first trusted owner.

## Production deployment

See [DEPLOYMENT.md](DEPLOYMENT.md) for production environment setup, HTTPS reverse-proxy requirements, health checks, backups, and release verification. [docker-compose.production.yml](docker-compose.production.yml) binds the API to loopback and leaves PostgreSQL unpublished. The existing docker-compose.yml is for local development and publishes PostgreSQL/API ports; do not use it directly as a public production stack.
