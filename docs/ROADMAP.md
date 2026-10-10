# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Foundation/identity/CRM — previously green in GitHub Actions; PostgreSQL/Docker pending.
2. Equipment/service catalog — previously green in GitHub Actions; PostgreSQL migration pending.
3. Agreement lifecycle, immutable proposal snapshots, acceptance and audit — previously green in GitHub Actions.
4. Team administration and session revocation — previously green in GitHub Actions.
5. Maintenance schedules and work-order dispatch/checklists — CI suite green; PostgreSQL migration and multi-process race verification pending.
6. Billing schema (invoices, invoice lines, payment ledger, idempotency and audit events) — IN_PROGRESS in current commit.
7. Invoice API workflows and payment settlement — PLANNED for next small commit.
8. Renewal workflows and durable notifications/outbox — PLANNED.
9. Reporting, imports, exports, integrations and webhooks — PLANNED.
10. Final PostgreSQL integration tests, Docker runtime, security/performance review and backend completion review — PLANNED.

Dependencies: identity/tenant boundaries precede every domain; customer/location and agreements precede billing; work-order completion feeds service history and billing. Recurring billing is blocked on a documented definition of agreement total versus installment amount.
