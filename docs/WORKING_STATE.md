# Working state

- Active task: CSV export endpoints.
- Routes: GET /api/v1/exports/customers.csv, invoices.csv, work-orders.csv, agreements.csv.
- Acceptance: current company scope, filters/date validation, max 10,000 rows, CSV attachment response, formula injection mitigation for text cells, invoice paid/balance from payment ledger.
- Current commit adds app/api/exports.py, test coverage, main registration and checkpoint docs.
- CI finding: removed the unused UUID import in app/api/exports.py. Next safe action: verify the fresh Ruff/pytest run, then add PostgreSQL migration execution to GitHub Actions.
