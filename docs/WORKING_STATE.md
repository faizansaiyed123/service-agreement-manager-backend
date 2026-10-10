# Working state

- Active task: agreement renewal offer API.
- Current code: renewal schemas/routes, main registration, API workflow/tenant-isolation tests, progress checkpoint.
- Acceptance criteria: offer requires currently active agreement and future successor term; snapshots all proposed terms and prices; only one open offer exists; accept creates a successor agreement from frozen offer data and records evidence; decline/cancel/expired offers cannot be accepted again; all routes are tenant-scoped.
- Renewal schema migration 0006 has passed GitHub Actions Ruff/pytest import checks; actual PostgreSQL migration execution remains outstanding.
- CI finding: renewal list handler now explicitly accepts the URL's `agreement_id` parameter. Verify fresh CI before starting notifications/outbox.
