# Progress

## Current milestone
PostgreSQL-backed migration verification in CI.

## Verified feature CI
- Maintenance/user suite: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38016919388 (success).
- Billing API/idempotency: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017375683 (success).
- Renewal API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017709123 (success).
- Notification worker tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018304748 (success).
- Reports API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018460376 (success).
- CSV export API: CI passed after removing one unused import; latest run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018628359 (success).

## Current change
CI now starts PostgreSQL 16, runs `alembic upgrade head` and `alembic current`, then Ruff and SQLite-backed API tests. This is the first automated real-PostgreSQL migration test in the project.

## PostgreSQL migration finding
The first PostgreSQL run caught a constraint-name collision between payments and notification outbox. The notification constraint now has a unique schema-level name in both ORM and migration; the fresh PostgreSQL CI run will verify the correction.

## Remaining verification limits
Live SMTP delivery and production Docker/deployment/monitoring remain unverified.
