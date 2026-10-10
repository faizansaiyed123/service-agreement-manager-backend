# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — CI green; tenant-scoped API regression suite green.
2. Equipment and service catalog — CI green.
3. Agreement lifecycle, immutable price snapshots, acceptance, version history, audit and explicit renewal offers — CI green.
4. Team management, session revocation, password change and password recovery — CI green.
5. Maintenance schedules, retry-safe generation worker, work-order lifecycle, technician assignment and checklist closeout — CI green.
6. Invoice draft/issue/void, immutable line prices, idempotent payment ledger, balances and receivables reporting — CI green.
7. Email notification outbox, leased worker, retries and dead-letter recovery — fake-sender tests green; actual SMTP delivery not verified.
8. Operational reports and CSV exports with tenant isolation and formula neutralization — CI green.
9. Production environment validation and Docker Compose workers — implementation committed; PostgreSQL 16/migration/drift and API tests are green. Docker Compose smoke started services and passed readiness; CI teardown completion is pending.
10. Branch and business-hours management — next feature slice.
11. Customer bulk imports, attachment metadata/storage and operational schedules — PLANNED.
12. Webhooks/integration credential lifecycle and delivery retry — PLANNED.
13. Dedicated PostgreSQL race/concurrency tests, actual SMTP provider verification, production deployment/security/performance review — PLANNED.

Automatic recurring invoices remain deferred until agreement total-versus-installment pricing semantics are explicitly defined. Do not claim production readiness until provider-backed delivery, deployed runtime, secrets/TLS and monitoring are verified.
