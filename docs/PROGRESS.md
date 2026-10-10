# Progress

## Current milestone
Schema drift detection in CI.

## Verified runs
- Notification worker/API tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018304748 (success).
- Reports API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018460376 (success).
- CSV exports: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018628359 (success).
- PostgreSQL 16 schema upgrade: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018805647 (success). All Alembic migrations applied and `alembic current` succeeded.

## Current change
Adds `alembic check` after applying migrations in the PostgreSQL CI job, to detect model/schema drift that previously wouldn't be caught by SQLite API tests or plain migration application.

## Verification
The drift-check step is awaiting its first run. PostgreSQL migration success is verified; schema drift check, production deployment and live SMTP remain pending until run/configured.
