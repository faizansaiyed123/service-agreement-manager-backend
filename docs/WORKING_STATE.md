# Working state

- Active task: automatic preventive-maintenance worker.
- Migration 0009_maint_gen_state is verified on PostgreSQL 16; ORM schema drift check is green.
- Current commit extracts maintenance context validation, work-order number allocation, recurring date calculation and event recording into app/services/maintenance.py. API routes now import these helpers from the service module.
- Next safe action: confirm this refactor's CI, then implement a bounded maintenance worker with persisted attempt/error state and idempotent work-order creation.
