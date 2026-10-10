# Progress

## Current milestone
Automatic preventive-maintenance worker — VERIFIED by GitHub Actions.

## Latest verification
Run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38019681845  
Commit: 92c2e41e72787fc7d8370dea193448ebcfe34f41

Passed:
- Ruff lint.
- Fresh PostgreSQL 16 database migration upgrade through head.
- Alembic current revision check.
- Alembic model/schema drift check.
- Full pytest API/regression suite, including worker retry/catch-up tests.

## Implemented
- Company-authenticated customer, contact and service-location APIs.
- Equipment and service catalog.
- Agreement draft/proposal/acceptance, snapshot pricing, cancellation, version/event history, explicit renewal offers.
- Company user administration and server-side session revocation.
- Maintenance schedules, work-order lifecycle and technician assignment/checklists.
- Automatic maintenance worker with locked due-schedule claims, bounded catch-up, unique occurrence protection, per-schedule error visibility and retry after data repair.
- Invoices and idempotent payment ledger, balance/overdue reports.
- Notification outbox and SMTP worker with bounded retries/dead-letter recovery.
- Operational reports and tenant-safe CSV exports.
- PostgreSQL 16 migration + Alembic drift checks in CI.

## Remaining limitations
- PostgreSQL migration/drift checks run on a real PostgreSQL 16 service. The full HTTP API suite still uses SQLite in CI; PostgreSQL concurrency/race tests remain to be added.
- Live SMTP/email provider delivery, deployment Docker runtime, TLS/secret management and production monitoring are not verified.
- SMS, invoice PDF delivery, refunds/credits, tax/discount support, and automatic recurring billing remain unimplemented.
- Password recovery/change, branch/region management, attachments, imports/webhooks and integration credential management remain planned.

## Next
Implement password change/session invalidation and account recovery as a focused security slice; validate its input and failure paths, then run CI.
