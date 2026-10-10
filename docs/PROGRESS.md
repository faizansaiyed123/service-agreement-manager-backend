# Progress

## Current milestone
Tenant-scoped operational reports.

## Verified prior feature runs
- Notification outbox schema: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017858281 (success).
- Notification API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018132338 (success).
- Notification worker/tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018304748 (success).

## Current change
Adds agreement lifecycle counts, billing receivables and overdue balance calculations, and work-order status/technician workload reporting. Calculation definitions and UTC as-of handling are returned/documented in response. Tenant filters are enforced in each query.

## Verification
Report tests await CI. CSV exports are the next slice after reports pass. PostgreSQL/Docker verification still needs a configured live environment.
