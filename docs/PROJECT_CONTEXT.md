# Project context

## Scope
Backend only for HVAC, plumbing and related trade contractors. Do not start frontend work without explicit approval.

## Stack
Python 3.12, FastAPI, Pydantic v2, SQLAlchemy 2.x, PostgreSQL, Alembic, PyJWT, pwdlib/Argon2, pytest/HTTPX, Ruff, Docker Compose.

## Architecture
Modular monolith; API modules own HTTP contracts, SQLAlchemy models represent durable state, and domain transitions are enforced in service/endpoint code and database constraints. Add repositories or background workers only where there is a real need.

## Domains currently present
Company/user authentication, current-company profile, customers/contacts/service locations, equipment/service catalog, and agreement lifecycle. Maintenance, work orders, billing, renewals, notifications, reporting, imports and integrations remain planned until implemented and verified.

## Security
Secrets belong in environment configuration, never in Git or checkpoint files. Access operations must scope tenant-owned data to the current user's company. Cross-company access should return 404 and have regression coverage. Production deployment still needs TLS, managed secrets, rate limiting, security review and operational policies.

## Database
PostgreSQL is authoritative. Use Alembic for schema changes; ORM create_all is test-only. Use UUID identifiers, UTC-aware timestamps, explicit constraints and indexes, and Decimal/Numeric for money.

## Agreement rules
Only draft agreements can be edited. Proposing captures an immutable snapshot of current contract terms and line prices. Catalog-backed lines use current catalog values when added and do not change when catalog prices later change. Agreement lifecycle changes are explicit and audited. Acceptance evidence is stored, but this app does not determine legal enforceability. Agreements are cancelled rather than deleted to preserve their history.

## Git and verification
Use focused conventional commits on main as requested. The latest main commit, CI result, migration state and known gaps must be checked rather than inferred.
