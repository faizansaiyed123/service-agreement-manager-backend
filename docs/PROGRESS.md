# Progress

## Current milestone
Webhook integrations and delivery infrastructure.

## Latest verification
- Customer-import ORM/migration drift was fixed and run 115 passed Ruff, PostgreSQL 16 migration upgrade, Alembic drift check, full pytest and Docker Compose readiness.
- Attachment Docker persistence was added with a dedicated `attachments_data` volume; Compose startup and migration checks have passed on the webhook-era runs.
- Webhook run 142 is validating the full endpoint/delivery stack after the test-collection and worker-lint fixes; its result is not yet complete at this checkpoint.

## Implemented
- Tenant-scoped identity, CRM, equipment/catalog, agreements, immutable snapshots, acceptance/audit and explicit renewals.
- User administration, session revocation, secure password change and hashed one-time password recovery with generic responses, cooldown, expiry and notification outbox delivery.
- Maintenance schedules, bounded/retryable schedule generation, work-order lifecycle, technician dispatch and completion checklists.
- Invoice lifecycle, idempotent payment ledger, receivables reports and tenant-safe CSV exports.
- Notification outbox and SMTP worker with bounded retries/dead-letter recovery. Password reset outbox rows are hidden from ordinary notification APIs.
- Production settings validation, timezone database dependency, Docker Compose maintenance worker and opt-in email worker, PostgreSQL 16 migration/drift checks and container readiness smoke job.
- Company branches with IANA time zones, one primary branch per company enforced by a partial unique index, seven-day local-time business hours, date closures and tenant-isolated CRUD.
- Recoverable, row-level customer bulk imports with preview, partial success, correction/retry and request-level `Idempotency-Key` replay protection.
- Tenant-scoped attachment metadata, local streaming storage, SHA-256 integrity tracking, size limits, upload/list/download/update/soft-delete APIs and persistent Docker storage.
- Tenant-scoped webhook endpoints with encrypted-at-rest secrets, event subscriptions, secret rotation, durable delivery/attempt records, signed HTTPS delivery, SSRF/private-network protection, backoff/dead-letter recovery and retry APIs.
- Webhook event emission is wired into customer creation/updates and bulk imports, agreement lifecycle transitions, work-order lifecycle/generation, invoice issuance/status changes and payment receipt.

## Current limitations
- Real SMTP delivery still needs provider credentials and provider-backed verification.
- Webhook run 142 must finish before this milestone is marked verified.
- API tests use SQLite; migrations are verified on PostgreSQL 16, but multi-process race tests for payments, schedule generation and webhook workers remain outstanding.
- Object-storage providers beyond the functional local storage backend, tax/discount configuration, refunds/credits, invoice PDF delivery, SMS and recurring invoices remain unimplemented.
- Production deployment, TLS/proxy/secrets setup and operational monitoring have not been verified.

## Next
After webhook CI is green, finish dedicated concurrency/security/performance testing and the final backend completion review.
