# Working state

- Active task: SMTP notification outbox worker.
- Notification schema and tenant-scoped API are already committed to main.
- Current files add app/workers/notifications.py and update progress/recovery notes.
- Worker claims queued/due rows under row locks and a lease, persists attempt numbers, uses SMTP configured by env, retries with bounded backoff, and moves exhausted sends to dead-letter status.
- No SMTP credentials were available; next commit must add fake-sender tests before this feature is considered verified.
