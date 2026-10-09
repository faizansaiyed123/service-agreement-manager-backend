# Working state

- Active task: maintenance schedule generation and work-order dispatch.
- Acceptance: schedule and work orders are tenant-scoped; customer/location/equipment/agreement references are verified; repeated generation of a schedule occurrence returns the existing work order; sequence identifiers are allocated from the company counter; only valid state transitions are accepted; only active company technicians can be assigned; technicians can work only their assignments; required checklist items must be completed before closeout.
- Current change adds operations models/schemas/routes, migration 0004, company work-order sequence counter, tests, and project checkpoints.
- CI scope includes the immediately preceding user-management/session changes; inspect the newest run after push and fix any failure before marking verified.
- PostgreSQL migration/concurrency tests and Docker runtime remain unverified.
- Next safe action: check CI output, fix issues, then implement billing.
