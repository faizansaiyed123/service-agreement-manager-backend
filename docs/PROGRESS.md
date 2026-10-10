# Progress

## Current milestone
Durable notification outbox and SMTP worker.

## Verified prior feature runs
- Renewal API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017709123 (success).
- Notification schema: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38017858281 (success).
- Notification API: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38018132338 (success).

## Implemented in main
Email notification enqueue/list/detail, idempotency-key conflict and replay behavior, attempt history, retry endpoint, SMTP worker, lease-based claims, bounded retries and dead-letter recovery. New tests exercise the queue through an injected sender and do not require SMTP credentials.

## Verification
Worker tests/CI are running in the current commit. Actual provider delivery remains dependent on SMTP environment configuration. PostgreSQL migrations, real row-lock concurrency, Docker deployment and monitoring are not yet verified.
