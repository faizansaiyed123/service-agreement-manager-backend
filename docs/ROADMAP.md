# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — VERIFIED.
2. Equipment and service catalog — VERIFIED.
3. Agreement lifecycle, immutable pricing snapshots, acceptance, version history, audit and explicit renewal offers — VERIFIED.
4. Team administration, session revocation, password change and password recovery — VERIFIED.
5. Maintenance schedules, retry-safe automatic generation, work-order dispatch, completion checklists and branch-aware routing — VERIFIED; dedicated PostgreSQL concurrency tests passed before the final extension pass.
6. Invoice lifecycle, immutable pricing, idempotent payments, tax/discount, refunds, credits, receivables reports and CSV exports — IMPLEMENTED; final combined CI verification in progress.
7. Notification outbox and SMTP delivery worker — IMPLEMENTED; fake-provider tests green, real SMTP provider delivery remains external verification.
8. Operational reports and safe CSV exports — VERIFIED.
9. Production configuration validation and Docker Compose worker runtime — IMPLEMENTED; PostgreSQL migration/drift checks and Compose smoke are part of CI.
10. Company branches, IANA timezone validation, local business hours, dated closures and single-primary invariant — IMPLEMENTED; existing companies receive a backfilled Head Office branch, while new registrations keep branch creation explicit.
11. Recoverable idempotent customer bulk import — VERIFIED.
12. Attachments with local storage, persistent Docker volume, S3-compatible backend and safe streaming downloads — IMPLEMENTED; final combined CI verification in progress.
13. Signed webhook integrations with encrypted endpoint secrets, durable delivery/retry and domain event emission — IMPLEMENTED; final combined CI verification in progress.
14. Recurring invoice schedules and billing worker — IMPLEMENTED; final combined CI verification in progress.
15. Durable SMS outbox/HTTP provider worker — IMPLEMENTED; final combined CI verification in progress.
16. Final security/concurrency/performance review and backend completion checkpoint — IN_PROGRESS.

No production-readiness claim is made for external provider delivery or deployment until real provider credentials, deployed runtime, TLS/secrets and monitoring are verified.