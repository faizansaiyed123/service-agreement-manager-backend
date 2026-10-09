# Roadmap

Feature states: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Backend foundation, identity and CRM — TESTING (source committed; CI and PostgreSQL verification pending).
2. Equipment and service catalog — PLANNED.
3. Agreement templates, agreement lifecycle, version snapshots, renewals and cancellation — PLANNED.
4. Maintenance schedules, idempotent work-order generation, dispatch and technician workflow — PLANNED.
5. Invoicing, immutable issued invoices, payment ledger and reconciliation — PLANNED.
6. Notifications/outbox, retry policy and provider adapters — PLANNED.
7. Reporting/export and operational metrics — PLANNED.
8. Integrations, webhook delivery, imports, idempotency and reconciliation — PLANNED.
9. End-to-end regression, security review, PostgreSQL migration tests, Docker runbook and backend completion review — PLANNED.

Dependencies: identity/company isolation precedes every domain. Customers and locations precede equipment and agreements. Agreements precede maintenance and recurring billing. Work orders feed service history and related invoicing. Outbox supports durable notifications/integrations; all implemented domains feed reports.
