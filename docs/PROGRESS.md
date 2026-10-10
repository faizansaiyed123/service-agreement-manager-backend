# Progress

## Current milestone
Notification outbox delivery worker.

## Verified prior feature runs
- Renewal API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017709123 (success).
- Notification outbox schema: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017858281 (success).
- Notification API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018132338 (success).

## Current change
Adds SMTP sending, row-locked outbox claiming, lease recovery, persistent attempt records, bounded exponential backoff with jitter and dead-letter state. Tests for send/retry/recovery are the next chunk.

## Verification limits
Current worker change awaits CI and focused tests. Actual delivery needs SMTP configuration. Live PostgreSQL lock semantics, Docker runtime, and production monitoring remain unverified.
