# Working state

- Active task: PostgreSQL migration verification in GitHub Actions.
- CSV exports are pushed and their Ruff/pytest CI run passed.
- Current change adds a PostgreSQL 16 service to CI, runs Alembic upgrade/current against that database, then runs Ruff and pytest.
- Acceptance: fresh PostgreSQL starts healthy, all revisions 0001 through head apply, current revision is reported, Ruff and SQLite API tests stay green.
- PostgreSQL CI exposed a name collision: payments and notification outbox both named a unique constraint `company_idempotency_key`. The notification constraint is renamed to `notification_company_idempotency_key` in both model and migration.
- PostgreSQL migration status remains unverified until the fresh workflow succeeds.
- Next safe action: inspect CI result and examine exact migration error logs if it fails; only after that add migration-drift checks or other features.
