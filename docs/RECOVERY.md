# Recovery guide

1. Inspect main, latest commit, Actions status, and the tree before editing.
2. Read PROJECT_CONTEXT.md, ROADMAP.md, PROGRESS.md, WORKING_STATE.md, and DECISIONS.md.
3. Inspect migrations with `alembic history`; on a live/test DB check with `alembic current`.
4. GitHub Actions applies all migrations to a fresh PostgreSQL 16 service using `alembic upgrade head`, reads the revision with `alembic current`, and runs `alembic check` to detect schema drift. Inspect each step before calling migration verification successful.
5. Read actual Ruff/test/migration logs before diagnosing a failing run. Do not infer success from a commit alone.
6. Resume at the earliest feature state not VERIFIED. Check commit and remote HEAD before retrying interrupted pushes.
7. Preserve unfinished work and never store credentials in checkpoints.

Local commands:
- `cp .env.example .env` and replace development secrets before use.
- `docker compose up --build -d`
- `docker compose exec api alembic upgrade head`
- `docker compose exec api alembic current`
- `docker compose exec api pytest`
- `docker compose exec api ruff check .`
- `docker compose down` (retains named database volume).

The notification worker requires valid SMTP configuration; its tests use a fake sender and do not prove provider delivery.
