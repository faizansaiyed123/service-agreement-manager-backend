# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — CI green; tenant-scoped API regressions green.
2. Equipment and service catalog — CI green.
3. Agreement lifecycle, snapshot pricing, acceptance and audit — CI green.
4. Team administration and server-side session revocation — CI green.
5. Maintenance schedules, work-order dispatch and automatic retry-safe schedule generation — VERIFIED by CI (run 38019681845).
6. Invoice lifecycle, payment ledger, idempotency and receivables metrics — CI green.
7. Renewal offer lifecycle — CI green.
8. Email outbox and worker retry/dead-letter mechanics — fake-sender tests green; live SMTP provider is not configured.
9. Operational reports and tenant-safe CSV exports — CI green.
10. Self-service password change and account recovery — PLANNED.
11. Service location/contact complete management, company branches/business hours, attachments and customer import/export jobs — PLANNED.
12. SMS/email provider delivery verification, webhooks/integrations and external credential status — PLANNED.
13. PostgreSQL concurrent worker/transaction tests, Docker runtime, production security/performance review — PLANNED.

Recurring invoice automation is intentionally deferred until agreement total-versus-installment semantics are explicit. Do not claim production readiness until live deployment checks complete.
