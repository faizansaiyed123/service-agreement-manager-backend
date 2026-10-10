# Working state

- Active task: invoice and payment workflows.
- Acceptance: tenant-scoped invoice references; Decimal/Numeric amounts; draft-only edits; issue/void transition checks; issued invoice immutability; partial/full payments; overpayment rejected; idempotency key replay returns one ledger row and key payload mismatch is rejected; event history and overdue query.
- Model/migration schema commit and cleanup commit passed Ruff/pytest CI.
- Current API chunk includes billing schemas/routes, main registration, API tests and checkpoint docs.
- PostgreSQL migration and concurrent transaction test are not verified in this environment.
- Latest finding: payment create endpoint must return HTTP 201 for new records; the retry path changes the response to 200. Follow-up applies this explicit status code.
- Next safe action: inspect the fresh CI result and resolve any further failures before proceeding.
