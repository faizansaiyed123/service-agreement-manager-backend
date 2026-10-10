# Working state

- Current verified feature slice: company branches, business hours and closures.
- CI run: https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38021794812. Ruff, PostgreSQL 16 upgrade through migration 0012, Alembic current/drift check, and pytest passed. Compose smoke built/started PostgreSQL + API + maintenance worker + opt-in email worker and passed /health/ready. The run was still finishing teardown at the time of last inspection.
- Migrations now end at revision 0012_primary_branch.
- Branch API: GET/POST /api/v1/branches, GET/PATCH /api/v1/branches/{id}, GET/PUT /api/v1/branches/{id}/business-hours, GET/POST /api/v1/branches/{id}/closures and DELETE the closure by ID.
- Branch hours are local wall-clock times in the branch's IANA timezone; weekdays are Monday=0 to Sunday=6; each weekly replacement must include each day exactly once; closed days have no times; closures apply for a full calendar day.
- Primary promotion locks the company, flushes the prior primary false before setting a new one true, and a partial unique index prevents more than one primary branch per company.
- Next feature: idempotent customer CSV bulk import with dry-run/preview, row-level validation and errors, tenant-scoped idempotency, bounded size and durable result summary.
- Known unverified areas: real SMTP provider delivery, dedicated cross-process PostgreSQL payment/schedule race tests, production deployment/TLS/secrets/monitoring, attachments, webhooks, tax/discount/refund/PDF/SMS and recurring invoices.
