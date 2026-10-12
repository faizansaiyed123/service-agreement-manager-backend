# Progress

## Current milestone
Backend feature completion — VERIFIED.

## Implemented backend surface
- Tenant-scoped authentication, rotating refresh sessions, logout/session revocation, password change and hashed one-time password recovery.
- Company profile, users/roles, CRM customers/contacts/service locations, equipment and service catalog.
- Agreements with immutable pricing snapshots, acceptance evidence, version history, audit events and explicit renewal offers.
- Maintenance schedules, retry-safe occurrence generation, work orders, technician assignment, completion checklists and branch-aware dispatch.
- Company branches with IANA time zones, weekly local business hours, dated closures and one-primary enforcement; existing companies receive a backfilled Head Office branch.
- Invoice lifecycle with immutable line pricing, tax/discount snapshots, idempotent payments, refunds, credits, balances, receivables reports and CSV exports.
- Recurring invoice schedules with monthly/quarterly/semi-annual/annual generation, optional auto-issue and durable worker state.
- Invoice PDF rendering and download.
- Durable email notification outbox with retry/dead-letter handling and SMTP worker.
- Durable SMS outbox with idempotency, lease recovery, retry/dead-letter behavior and configurable HTTP provider.
- Tenant-scoped customer bulk import with preview, row-level validation, partial success, correction/retry and Idempotency-Key replay protection.
- Tenant-scoped attachments with streaming local storage, SHA-256 integrity metadata, size limits, soft deletion, persistent Docker storage and S3-compatible object storage.
- Tenant-scoped webhook endpoints with encrypted secrets, event subscriptions, secret rotation, durable delivery attempts, HMAC signatures, HTTPS-only delivery, SSRF/private-network protection, backoff/dead-letter recovery and retry APIs.
- Domain webhook emission for customer, agreement, work-order, invoice and payment lifecycle events.
- Production configuration validation, PostgreSQL 16 migration/drift checks, Docker Compose workers, readiness/liveness endpoints and CI coverage.

## Final verification
GitHub Actions run 224 on commit 29ea07fd850e7699c0ba5947f5d6f3eaf27fdd1b completed successfully:
- Ruff passed.
- PostgreSQL 16 migrations and revision verification passed.
- Alembic ORM/database drift check passed.
- Full pytest suite passed.
- Dedicated PostgreSQL concurrency tests passed.
- Docker Compose API/worker startup, readiness and teardown smoke passed.

## External verification still required
- Real SMTP provider credentials and provider-backed delivery.
- Real SMS provider credentials/end-to-end delivery.
- Real S3-compatible credentials/end-to-end object storage.
- Production deployment, TLS/proxy configuration, secrets injection, monitoring and alerting.
