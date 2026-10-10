# Progress

## Current milestone
Durable notification outbox schema.

## Verified prior API slices
- Maintenance/user tests: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38016919388 (success).
- Billing schema: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017135881 (success).
- Billing API/payment idempotency: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017375683 (success).
- Renewal schema: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017492987 (success).
- Renewal API and explicit-list-path fix: see current main workflow for commit b465aed644026775aff0d188a15e9cee62f6f698.

## Current schema chunk
Adds email outbox state, company idempotency, scheduled delivery time, lease expiry, bounded attempt count and attempt history. SMTP connection settings are now environment-based. API/worker implementation follows in its own commit.

## Verification limitations
A configured SMTP provider is required for actual delivery. SMS is not included in this slice. Live PostgreSQL migrations, SMTP integration and Docker runtime need environment-backed verification.
