# Roadmap

Feature states: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Backend foundation, identity and CRM — VERIFIED by the current GitHub Actions suite; PostgreSQL/Docker verification remains pending.
2. Equipment and service catalog — VERIFIED by GitHub Actions; PostgreSQL migration execution remains pending.
3. Agreement lifecycle, immutable proposal snapshots, acceptance evidence, explicit status transitions and audit history — IN_PROGRESS until current CI completes.
4. Agreement amendments, template versioning, automatic expiration and renewal workflows — PLANNED.
5. Maintenance schedules, idempotent work-order generation, dispatch and technician workflow — PLANNED.
6. Invoicing, immutable issued invoices, payment ledger and reconciliation — PLANNED.
7. Notifications/outbox, retry policy and provider adapters — PLANNED.
8. Reporting/export and operational metrics — PLANNED.
9. Integrations, webhook delivery, imports, idempotency and reconciliation — PLANNED.
10. End-to-end regression, security review, PostgreSQL migration tests, Docker runbook and backend completion review — PLANNED.

Dependencies: identity/company isolation precedes every domain. Customers and locations precede equipment and agreements. Agreements precede maintenance and recurring billing. Work orders feed service history and invoicing. Outbox supports durable notifications and integrations; implemented domains feed reporting.
