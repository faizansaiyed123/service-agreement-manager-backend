# Progress

## Current milestone
Invoice and payment API workflows.

## Verified feature runs
- Maintenance + session suite: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38016919388 (success).
- Billing schema import/lint verification: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017135881 (success).

## Implemented source
Tenant-scoped identity, CRM, assets, agreements, maintenance and work-order dispatch. Billing schema now has invoice and invoice-line snapshots, payment ledger/idempotency fingerprint and audit events. The current API chunk adds invoice draft CRUD/list, issue/void workflows, derived payment balances/overdue visibility, append-only payment recording, idempotent retries, payment history and invoice event history.

## Verification
Billing API routes/tests await GitHub Actions. PostgreSQL migration execution, database locking races, Docker startup and production deployment remain unverified.

## Deferred deliberately
Taxes/discounts, refunds/credits, PDF delivery and automatic recurring invoice generation remain out of scope for this billing slice. Agreement total-vs-installment pricing must be defined before recurring invoice generation.
