# Progress

## Current milestone
Production configuration and Docker runtime hardening.

## Latest verified run
- Recovery and PostgreSQL migration 0010: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38020480557 (success).
- Latest runtime run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38020974685 — Ruff, PostgreSQL 16 upgrade/current/drift check and full pytest passed; Docker Compose built and started the API plus maintenance/email workers and the health readiness smoke check passed. Final cleanup is still completing at checkpoint time.

## Implemented
- Tenant-scoped identity, CRM, equipment/catalog, agreement lifecycle, immutable snapshots, acceptance/audit and explicit renewals.
- Team administration, self-service password change, and hashed one-time password recovery with cooldown, expiry, generic response, email outbox queueing and session revocation.
- Maintenance schedules, bounded automatic generation worker with retry/error visibility, work-order lifecycle, technician dispatch and checklists.
- Invoice lifecycle and idempotent payment ledger, reporting, and tenant-safe CSV exports.
- Notification outbox/SMTP worker with retries and dead-letter recovery. Password reset outbox records are hidden from normal notification read endpoints.
- CI PostgreSQL 16 migration upgrade and Alembic drift check.
- Docker Compose services for API/database plus maintenance worker; SMTP notification worker is enabled with the email profile.

## Remaining limitations
- SMTP provider delivery is not verified without real credentials/provider access.
- API regression tests run on SQLite; migrations run on PostgreSQL 16 in CI, but concurrent multi-worker/payment race tests still need dedicated coverage.
- Tax/discounts, refunds/credits, invoice PDF delivery, SMS, bulk imports, attachment storage, branch/business-hours management and integration/webhook delivery remain unimplemented.
- Production deployment, external TLS/proxy/secrets configuration and monitoring have not been verified.

## Next
Implement company branch/location and business-hours management as a focused domain slice, then add tests for tenant isolation, time-zone handling and invalid hours.
