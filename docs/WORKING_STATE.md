# Working state

- Latest verified commit includes account recovery API, migration 0010 and recovery tests.
- Verification run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38020480557 — Ruff, PostgreSQL 16 migration upgrade, Alembic current/check and pytest all passed.
- Routes: POST /api/v1/auth/forgot-password (generic 202 response) and POST /api/v1/auth/reset-password (single-use token, 204 success). Token hashes are persisted; raw tokens are sent only in the queued email and never returned via API.
- Password-reset notification records are excluded from general notification listing, detail, attempts and retry APIs so their reset URLs cannot be retrieved by ordinary company users.
- Current focus: validate production SMTP + HTTPS reset URL settings, and start both background workers in Docker Compose. No SMTP provider is configured here.
- Known unverified work: actual provider email delivery, container lifecycle, PostgreSQL concurrent request races, attachment/object storage and external webhooks.
