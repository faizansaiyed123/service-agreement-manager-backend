# Working state

- Active task: reporting API.
- Current endpoints: agreement summary, invoice receivables, work-order status and technician workload.
- Acceptance: each query scopes by company; monetary totals use Decimal values; overdue calculations use UTC date and the current ledger balance; optional date ranges are validated; report response includes calculation context.
- Current change adds report schemas/routes/tests, main router registration and checkpoints.
- Next safe action: inspect CI on this commit, fix failures, then add CSV exports with formula-injection protection.
