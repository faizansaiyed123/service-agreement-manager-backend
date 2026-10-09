# Working state

- Active task: tenant-scoped user administration and session invalidation.
- Acceptance: owners/admins can create staff; only owners can grant owner/admin; user list/get is tenant scoped; password reset revokes active sessions; logout immediately invalidates access and refresh tokens.
- Current change: user router/schema/tests, auth dependency session check, main router registration, progress and recovery state.
- Verified agreement run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/37959977883.
- PostgreSQL/Alembic live migration, Docker runtime and concurrent behavior are not yet verified.
- Next safe action: inspect CI for this commit, fix issues, then continue to maintenance scheduling and work orders.
