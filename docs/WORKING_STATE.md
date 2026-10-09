# Working state

- Active task: Agreement lifecycle vertical slice.
- Acceptance: tenant-scoped agreements; verified customer/location ownership; Decimal/Numeric pricing; price snapshots; draft-only editing; conflict responses for invalid transitions; acceptance evidence; version and event persistence; regression tests.
- Files in this slice: agreement models/schemas/API, Alembic revision 0003, app/model registration, tests, roadmap/progress/context.
- Migration: 0003_agreements depends on 0002_assets_catalog; PostgreSQL execution remains to be verified.
- Checks: current GitHub Actions run will execute Ruff and Pytest after the push.
- No local working tree or live PostgreSQL session is attached to the GitHub connector; source writes are made through the Git database API.
- Next safe action: inspect CI on this commit and fix any failing check before proceeding to maintenance scheduling.
