# Project context

## Scope
Backend only. The product serves HVAC, plumbing, and related-trade contractors. Frontend work is out of scope until separately authorized.

## Stack and architecture
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, Alembic, PyJWT, pwdlib/Argon2, pytest/HTTPX, Ruff and Docker Compose. Use a modular monolith. Routers handle HTTP validation and response mapping; domain rules belong in business services as modules expand.

## Current implementation boundary
The initial slice contains health checks, company registration/current-company management, authentication/session refresh and revocation, customers, contacts, and service locations. Equipment, service catalog, agreement lifecycle, preventive maintenance, work orders, invoicing/payments, notifications, reports and integrations are not complete until their API, migration and tests have been committed and verified.

## Security
Do not commit credentials or .env. JWT secret is environment-configured. Use short-lived access tokens and single-use rotating refresh tokens. Tenant-owned reads/writes must scope by the authenticated company. Add explicit cross-company denial tests for each domain. Production still requires TLS, managed secrets, rate limits, and deployment hardening.

## Database
PostgreSQL is authoritative; Alembic revisions manage schema changes. Use UUID identifiers, UTC-aware timestamps, database constraints and indexed tenant scopes. Financial fields must use Decimal/Numeric. ORM create_all is only a test fixture mechanism.

## Quality and Git
Ruff and pytest run in CI on main. Do not claim checks passed without evidence from output or workflow logs. Commit small verified slices; never force-push or reset shared history.
