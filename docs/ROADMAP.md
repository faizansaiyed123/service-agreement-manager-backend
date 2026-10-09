# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Backend foundation, identity and CRM — previously green in GitHub Actions; PostgreSQL/Docker verification pending.
2. Equipment and service catalog — previously green in GitHub Actions; PostgreSQL migration execution pending.
3. Agreement lifecycle, snapshots, acceptance and audit history — green in GitHub Actions; PostgreSQL verification pending.
4. Team administration and server-side session revocation — included in the current CI scope.
5. Maintenance schedules and retry-safe work-order generation — included in the current CI scope.
6. Work-order dispatch, technician assignment, completion checklists and service history — included in the current CI scope.
7. Invoicing, immutable issued invoices, payment ledger, balance calculations and reconciliation — PLANNED.
8. Renewals, cancellation policy, durable notification/outbox processing — PLANNED.
9. Reporting/exports and integrations/webhooks/imports — PLANNED.
10. End-to-end regression, PostgreSQL migrations, Docker, security, performance and final completion review — PLANNED.

Dependencies: identity and tenant boundaries precede all modules; customers/locations precede equipment, agreements and jobs; agreements may drive maintenance and recurring billing; work-order completion feeds service history and billing; outbox supports resilient notifications and integrations.
