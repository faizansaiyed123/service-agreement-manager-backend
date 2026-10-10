# Progress

## Current milestone
Tenant-scoped CSV exports.

## Verified prior feature runs
- Notifications API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018132338 (success).
- Notification worker: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018252622 (success).
- Notification worker tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018304748 (success).
- Operational reports: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018460376 (success).

## Current change
Adds CSV exports for customers, invoices, work orders and agreements. Exports use tenant filtering, filter/range validation, bounded pagination and spreadsheet-formula neutralization on string cells. Invoice export derives amount paid from the payment ledger and calculates outstanding balance.

## Verification
The first export CI run stopped at Ruff due to one unused UUID import; it has been removed in this follow-up. Pytest has not yet run for the export change. PostgreSQL migrations have not yet been applied to a live PostgreSQL instance; a PostgreSQL-backed CI migration job is the next infrastructure step.
