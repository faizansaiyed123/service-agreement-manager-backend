# Progress

## Current milestone
Explicit agreement renewal offers.

## Verified feature runs
- User and operations suite: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38016919388 (success).
- Billing schema/lint slice: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017135881 (success).
- Billing API/idempotency suite: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017375683 (success).

## Renewal schema committed in current slice
An agreement renewal offer stores the proposed term dates, expiry date, immutable JSON pricing/terms snapshot, explicit status, acceptance evidence, and optional successor agreement link. API workflows are the next small feature commit.

## Verification limitations
The billing and renewal schema migrations are in history but have not yet been executed against a live PostgreSQL instance in this environment. CI tests currently use SQLite for API regression; PostgreSQL locking and production Docker remain unverified.

## Product rules
Do not renew automatically without explicit accepted terms. Agreement renewal will clone proposed price snapshots into a successor agreement only after acceptance. Automatic recurring billing remains deferred until pricing-period semantics are explicit.
