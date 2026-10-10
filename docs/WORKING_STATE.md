# Working state

- Active task: automatic maintenance schedule worker.
- Current commit adds nullable last_generation_attempt_at and last_generation_error fields and Alembic revision 0009.
- PostgreSQL CI, Alembic current and schema drift were green before this migration.
- Next feature commit will add a bounded worker that locks due schedules, validates company/customer/location/equipment/agreement relationships, creates a work order per due occurrence, advances next_due_date, and persists per-schedule failure information without losing other schedules in the batch.
- Acceptance: duplicate generation remains prevented by database uniqueness and row locks; failures are observable and retryable; no schedule is advanced after failed generation.
