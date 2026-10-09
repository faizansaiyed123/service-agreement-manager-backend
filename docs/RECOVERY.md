# Recovery guide

1. Inspect main, the latest commit, Actions status and the tree before editing.
2. Read PROJECT_CONTEXT.md, ROADMAP.md, PROGRESS.md, WORKING_STATE.md and DECISIONS.md.
3. Check the migration revision with alembic current and migration order with alembic history.
4. Inspect CI run logs before diagnosing a failed job; do not infer success from a commit.
5. Resume at the earliest feature state not marked VERIFIED. Inspect interrupted operations before repeating them.
6. Preserve unfinished work and never store secrets in checkpoint files.

Local commands:
- Copy .env.example to .env and replace the sample JWT secret before use.
- docker compose up --build -d
- docker compose exec api alembic current
- docker compose exec api pytest
- docker compose exec api ruff check .
- docker compose down (retains the named database volume).

If a push or job was interrupted, inspect the main branch head and the corresponding Actions run first.
