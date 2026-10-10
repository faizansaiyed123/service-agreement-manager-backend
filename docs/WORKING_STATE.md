# Working state

- Active task: add Alembic schema drift check to PostgreSQL CI.
- PostgreSQL 16 CI run 38018805647 passed: migration upgrade and current revision commands both succeeded; Ruff and pytest passed.
- Current change inserts `alembic check` after `alembic current` in CI and updates progress/recovery notes.
- Acceptance: a fresh PostgreSQL database upgrades successfully; Alembic confirms mapped models do not require ungenerated schema changes; Ruff and pytest remain green.
- Next safe action: inspect the drift check result and correct any actual mismatch with a focused model/migration change.
