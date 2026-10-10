# Working state

- Active task: billing schema/migration.
- Current slice defines invoice headers, line-item price snapshots, payment ledger, idempotency constraints, invoice audit events, and company invoice sequence.
- Migration revision: 0005_billing after 0004_operations.
- API routes and payment behavior tests are not part of the schema-only commit; implement them next after inspecting CI.
- Automated recurring invoices are intentionally deferred until price-period semantics are defined explicitly; tax/discounts/refunds/credits are also out of this slice.
- Next safe action: inspect CI on the schema commit; then add invoice create/edit/issue/void and payment APIs with retry-safe idempotency.
