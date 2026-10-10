# Working state

- Latest code milestone: production settings + Docker Compose workers + Compose smoke CI.
- Last main API test/migration/drift checks passed in GitHub Actions run https://github.com/faizansaiyed123/service-agreement-manager-backend/actions/runs/38020974685.
- The Compose smoke job on that run successfully built and started PostgreSQL, API, maintenance-worker and notification-worker, then passed the /health/ready check. Container teardown was still completing at checkpoint time.
- CORS settings now accept both JSON arrays and the existing comma-separated sample format; the Docker failure revealed Pydantic was trying to JSON-decode the CSV-style setting.
- Production settings require a long unique JWT secret, non-debug mode, SMTP host/from address, STARTTLS, matching SMTP credentials and a public HTTPS password reset page URL.
- Docker Compose always starts the maintenance worker. Email delivery worker is opt-in via the email profile, since it needs actual SMTP config.
- Next feature: company branch/location and business-hours management. Keep it modular with tenant-scoped CRUD, time-zone aware business hours, DB migration and focused tests.
- Unverified: real SMTP inbox delivery, multi-process PostgreSQL concurrency/race tests, actual deployment/TLS/secrets/monitoring, attachments, import/webhooks, tax/discount/refund/PDF/SMS and recurring invoices.
