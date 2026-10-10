# Working state

- Active task: invoice and payment workflows.
- Acceptance: tenant-scoped invoice references; Decimal/Numeric amounts; draft-only edits; issue/void transition checks; issued invoice immutability; partial/full payments; overpayment rejected; idempotency key replay returns one ledger row and key payload mismatch is rejected; event history and overdue query.
- Model/migration schema commit and cleanup commit passed Ruff/pytest CI.
- Current API chunk includes billing schemas/routes, main registration, API tests and checkpoint docs.
- PostgreSQL migration and concurrent transaction test are not verified in this environment.
- Next safe action: inspect the current CI log, correct any failures, then commit a focused follow-up.
