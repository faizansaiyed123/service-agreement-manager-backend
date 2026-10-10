# Working state

- Active task: automatic preventive-maintenance worker.
- Maintenance service layer is extracted and passing CI after removal of one unused import.
- Current code adds app/workers/maintenance.py, ScheduleRead generation diagnostics, bounded catch-up, per-schedule savepoint/error isolation, work-order uniqueness recovery, worker tests and run instructions.
- Worker test expectation: failed customer validation leaves schedule cursor unchanged and stores last_generation_error; success clears it and advances recurrence; future due dates are left unclaimed; backlog catch-up is limited per run.
- Next action: check CI for actual Ruff, migration/drift, and pytest outcomes; fix any findings before declaring scheduler verified.
