# Roadmap

States: PLANNED, IN_PROGRESS, IMPLEMENTED, TESTING, VERIFIED, COMMITTED, PUSHED, BLOCKED.

1. Identity/company and CRM — CI green; tenant-scoped API regression coverage.
2. Equipment and service catalog — CI green.
3. Agreement lifecycle, immutable pricing snapshots, acceptance, version history, audit and explicit renewal offers — CI green.
4. Team administration, session revocation, password change and password recovery — CI green.
5. Maintenance schedules, retry-safe automatic generation and work-order dispatch/checklists — CI green; dedicated multi-process PostgreSQL race tests pending.
6. Invoice lifecycle, immutable line pricing, idempotent payments, balance calculations and receivables reports — CI green; payment race tests pending.
7. Notification outbox and SMTP delivery worker — fake-sender retry/dead-letter tests green; real SMTP delivery unverified.
8. Operational reports and safe CSV exports — CI green.
9. Production configuration validation and Docker Compose worker runtime — CI PostgreSQL migration/drift checks and Compose readiness smoke pass; external deployment not performed.
10. Company branches, IANA timezone validation, weekly local-time opening hours, dated closures and single-primary invariant — API tests and PostgreSQL migration/drift checks green.
11. Idempotent customer bulk import with preview/row-level validation — VERIFIED by ORM/migration drift check, full pytest and Compose smoke.
12. Attachment metadata/local storage, persistent Docker storage and import recovery improvements — IMPLEMENTED; PostgreSQL migration and Compose startup verified, full attachment lifecycle is covered by API tests.
13. Webhooks/integration credential lifecycle and delivery retry — IN_PROGRESS; endpoint management, encrypted secrets, event subscriptions, signed delivery worker, SSRF controls and domain event emission implemented; final CI verification pending.
14. Dedicated concurrency/security/performance testing, SMTP provider integration test and final backend completion review — PLANNED.

Automatic recurring invoices remain deferred until agreement total-versus-installment semantics are explicitly defined. No production-readiness claim until provider-backed delivery, deployed runtime, TLS/secrets and monitoring are verified.
