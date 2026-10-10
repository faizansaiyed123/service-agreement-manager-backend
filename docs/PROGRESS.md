# Progress

## Current milestone
Security recovery flows and production runtime hardening.

## Latest verified run
- Password recovery + migration 0010: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38020480557 (success).
- Passing checks: Ruff, PostgreSQL 16 migration upgrade, Alembic current revision, Alembic model/schema drift check, and full pytest suite.

## Implemented
- Tenant-scoped identity, CRM, equipment/catalog, agreements and renewal offers.
- User administration, password change, single-use expiring password recovery, generic forgot-password response, email outbox integration, and session revocation.
- Maintenance schedule/worker generation and work-order dispatch/checklists.
- Invoices, idempotent payment ledger, receivables report and CSV exports.
- Notification outbox with SMTP worker, bounded retries and dead-letter recovery; password-reset notifications are hidden from general notification APIs.

## Current limitations
- SMTP inbox delivery has not been verified against a real provider; recovery emails remain queued until the notification worker is deployed with working SMTP settings.
- Docker Compose currently starts the API and database but does not supervise background workers as services.
- HTTP API tests use SQLite; PostgreSQL migration/drift checks run on PostgreSQL 16. Multi-process concurrency tests remain outstanding.
- Taxes/discounts, refunds/credits, recurring invoices, SMS, attachment storage, webhooks/integrations and customer bulk imports remain unimplemented.

## Next
Validate production SMTP/reset URL settings, add worker services to Docker Compose with shared environment/database configuration, then test the complete container lifecycle.
