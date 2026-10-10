# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity, company and CRM — CI green; API tests use SQLite, migrations use PostgreSQL 16 CI.
2. Equipment and service catalog — CI green.
3. Agreement lifecycle, acceptance snapshots and audit — CI green.
4. User administration and session revocation — CI green.
5. Maintenance schedules and work-order dispatch — manual generation and workflows are green; automatic recurring scheduler is IN_PROGRESS.
6. Billing and idempotent payments — CI green; PostgreSQL schema/drift check green.
7. Renewal offer lifecycle — CI green.
8. Notification outbox/worker — fake-sender tests green; live SMTP not configured.
9. Operational reports and tenant-safe CSV exports — CI green.
10. Automatic preventive-maintenance worker and retry/error observability — IN_PROGRESS.
11. Account recovery, branch/business-hours administration, attachments, integrations/webhooks, and import/export jobs — PLANNED.
12. Final security, Docker runtime, PostgreSQL concurrency, performance and deployment review — PLANNED.

Recurring invoice automation remains deferred until pricing-period semantics are defined; external-provider delivery is not claimed without live configuration.
