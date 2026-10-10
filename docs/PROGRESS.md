# Progress

## Current milestone
Invoice and payment ledger foundation.

## Verified API slices
- Identity/user administration CI: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/37961486405 (success).
- Agreement lifecycle + audit ordering: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/37959977883 (success).
- Maintenance/user integrated test suite: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38016919388 (success).

## Billing schema added in current commit
Invoice headers and immutable line snapshots, payment ledger with company-scoped idempotency key and request fingerprint, invoice audit events, and company invoice-number sequence. API routes and transaction/idempotency tests are the next bounded chunk.

## Verification
The schema commit's GitHub Actions status will be inspected after push. PostgreSQL migration execution, live database transaction/concurrency checks, Docker runtime and production are not verified here.

## Product boundary
Tax/discount configuration, refunds/credits, and automatic recurring invoice generation remain deferred. Current agreement data doesn't distinguish per-period price from full-term total; recurring billing must not guess.
