# Progress

## Current milestone
Schema drift detection in CI.

## Verified runs
- Notification worker/API tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018304748 (success).
- Reports API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018460376 (success).
- CSV exports: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018628359 (success).
- PostgreSQL 16 schema upgrade: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018805647 (success). All Alembic migrations applied and `alembic current` succeeded.

## Current change
`alembic check` found a missing ORM-requested index on `agreements.service_location_id`. A new forward migration 0008 adds `ix_agreements_service_location_id`; prior applied migrations remain unchanged.

## Verification
The migration and drift-check rerun is pending. PostgreSQL migration up to 0007 previously succeeded; schema drift check, production deployment and live SMTP remain pending until verified.
