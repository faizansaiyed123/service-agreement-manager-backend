# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — CI suite green; PostgreSQL/Docker verification pending.
2. Equipment and service catalog — CI suite green; PostgreSQL migration pending.
3. Agreement lifecycle, terms/price snapshots, acceptance and audit — CI suite green.
4. Team management and session revocation — CI suite green.
5. Maintenance schedules, idempotent work-order generation and technician workflow — CI suite green; PostgreSQL multi-process concurrency pending.
6. Invoice lifecycle, payment ledger, idempotency, balance/overdue reporting — CI suite green.
7. Renewal offer schema — IN_PROGRESS for API acceptance/decline workflows.
8. Notification outbox and delivery attempts — PLANNED.
9. Operational reports and CSV exports — PLANNED.
10. Integrations/webhooks, import/export recovery and reconciliation — PLANNED.
11. PostgreSQL migration/runtime tests, security/performance review and backend completion audit — PLANNED.

Renewal accepts must be explicit and snapshot all terms/prices. Taxes, refunds/credits, recurring invoice generation and actual email/SMS delivery need documented rules or provider configuration and are not claimed complete.
