# Progress

## Current milestone
Company branches, local business hours and dated closures.

## Latest verification
- Feature/runtime CI: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38021794812 — Ruff, PostgreSQL 16 migration upgrade through revision 0012, Alembic drift check and full pytest passed. Docker Compose built/started the API and both workers and the readiness probe passed; cleanup was finishing at checkpoint time.

## Implemented
- Tenant-scoped identity, CRM, equipment/catalog, agreements, immutable snapshots, acceptance/audit and explicit renewals.
- User administration, session revocation, secure password change and hashed one-time password recovery with generic responses, cooldown, expiry and notification outbox delivery.
- Maintenance schedules, bounded/retryable schedule generation, work-order lifecycle, technician dispatch and completion checklists.
- Invoice lifecycle, idempotent payment ledger, receivables reports and tenant-safe CSV exports.
- Notification outbox and SMTP worker with bounded retries/dead-letter recovery. Password reset outbox rows are hidden from ordinary notification APIs.
- Production settings validation, timezone database dependency, Docker Compose maintenance worker and opt-in email worker, PostgreSQL 16 migration/drift checks and container readiness smoke job.
- Company branches with IANA time zones, one primary branch per company enforced by a partial unique index, seven-day local-time business hours, date closures and tenant-isolated CRUD.

## Current limitations
- Real SMTP delivery still needs provider credentials and provider-backed verification.
- API tests use SQLite; migrations are verified on PostgreSQL 16, but multi-process race tests for payments and schedule generation remain outstanding.
- Bulk customer imports, attachment storage, webhooks/integrations, tax/discount configuration, refunds/credits, invoice PDF delivery, SMS and recurring invoices remain unimplemented.
- Production deployment, TLS/proxy/secrets setup and operational monitoring have not been verified.

## Next
Implement idempotent customer bulk import with row-level validation and a recoverable import result, then run the complete CI/Compose suite before moving to webhooks and final concurrency review.
