# Working state

- Active task: add Alembic schema drift check to PostgreSQL CI.
- PostgreSQL 16 CI run 38018805647 passed: migration upgrade and current revision commands both succeeded; Ruff and pytest passed.
- Current change inserts `alembic check` after `alembic current` in CI and updates progress/recovery notes.
- Drift check finding: ORM metadata expects `ix_agreements_service_location_id`, missing from existing 0003 revision. Added new forward-only migration 0008 rather than modifying historical migration files.
- Acceptance: a fresh PostgreSQL database upgrades successfully through 0008; Alembic reports no model drift; Ruff and pytest remain green.
- Next safe action: inspect the next CI run. If another drift appears, add a narrow migration and preserve history.
