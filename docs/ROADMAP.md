# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company, CRM and tenant isolation — CI green.
2. Equipment and service catalog — CI green.
3. Agreement lifecycle, immutable price snapshots, acceptance and audit — CI green.
4. Team administration, session revocation and self-service password change — CI green.
5. Maintenance scheduling, automatic bounded catch-up worker and work-order dispatch — CI green; PostgreSQL multi-worker races need a dedicated integration test.
6. Invoice lifecycle, immutable lines, idempotent payment ledger and receivables reports — CI green.
7. Explicit agreement renewal offers — CI green.
8. Notification outbox and retry/dead-letter worker — fake-sender tests green; real SMTP provider still unverified.
9. Tenant-safe operational reports and CSV exports — CI green.
10. Password recovery with hashed one-time expiring tokens, generic responses, cooldown, outbox delivery and session revocation — VERIFIED (CI run 38020480557).
11. Production configuration validation and Docker Compose worker supervision — IN_PROGRESS.
12. Attachment metadata/storage, company branch/business-hours administration and customer bulk imports — PLANNED.
13. Webhooks/integration credential lifecycle and delivery retry — PLANNED.
14. PostgreSQL concurrency, Docker end-to-end runtime, security/performance and final backend completion audit — PLANNED.

Automatic recurring billing remains deferred until agreement total-versus-installment semantics are explicitly defined. Production readiness is not claimed until deployed runtime and provider-backed email checks pass.
