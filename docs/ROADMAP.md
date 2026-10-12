# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — VERIFIED.
2. Equipment and service catalog — VERIFIED.
3. Agreement lifecycle, immutable pricing snapshots, acceptance, version history, audit and explicit renewal offers — VERIFIED.
4. Team administration, session revocation, password change and password recovery — VERIFIED.
5. Maintenance schedules, retry-safe automatic generation, work-order dispatch, completion checklists and branch-aware routing — VERIFIED; PostgreSQL concurrency tests passed.
6. Invoice lifecycle, immutable pricing, idempotent payments, tax/discount, refunds, credits, receivables reports and CSV exports — VERIFIED.
7. Notification outbox and SMTP delivery worker — VERIFIED at application/test level; real provider delivery remains external verification.
8. Operational reports and safe CSV exports — VERIFIED.
9. Production configuration validation and Docker Compose worker runtime — VERIFIED by PostgreSQL migration/drift checks and Compose smoke.
10. Company branches, IANA timezone validation, local business hours, dated closures and single-primary invariant — VERIFIED; existing companies receive a backfilled Head Office branch, while new registrations keep branch creation explicit.
11. Recoverable idempotent customer bulk import — VERIFIED.
12. Attachments with local storage, persistent Docker volume, S3-compatible backend and safe streaming downloads — VERIFIED at application/test level; real object-storage delivery remains external verification.
13. Signed webhook integrations with encrypted endpoint secrets, durable delivery/retry and domain event emission — VERIFIED at application/test level, including recurring invoice creation/issuance events.
14. Recurring invoice schedules and billing worker — VERIFIED.
15. Durable SMS outbox/HTTP provider worker — VERIFIED at application/test level; real provider delivery remains external verification.
16. Final security/concurrency/performance review and backend completion checkpoint — VERIFIED by final CI run 244.

No production-readiness claim is made for external provider delivery or deployment until real provider credentials, deployed runtime, TLS/secrets and monitoring are verified.
