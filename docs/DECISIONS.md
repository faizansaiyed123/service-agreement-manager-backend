# Architecture decisions

## ADR-001: Modular monolith
Use one FastAPI deployment with bounded modules and a single PostgreSQL database before considering services.

## ADR-002: PostgreSQL and Alembic
PostgreSQL is the source of truth. Schema changes are explicit Alembic revisions; ORM create_all must not manage production schema.

## ADR-003: Tenant isolation
Every tenant-owned record carries company_id. Endpoint queries scope by authenticated company and return 404 for another tenant's resource to avoid existence disclosure. Composite tenant-aware foreign keys remain a strengthening task for later domain migrations.

## ADR-004: Authentication
Use pwdlib's Argon2 password hashing and signed JWTs. Refresh tokens rotate on use, with the active JTI stored on a server-side session. Logout revokes refresh sessions; access tokens expire quickly and are not immediately revoked by logout.

## ADR-005: Incremental delivery
Code is not verified merely because it exists. Automated tests and PostgreSQL-backed migration tests must complete before calling a feature verified. Progress docs distinguish implementation, verification, commit, and push.
