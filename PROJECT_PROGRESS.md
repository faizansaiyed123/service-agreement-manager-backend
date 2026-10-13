# Project Progress

## Overall status
Backend is verified at the application/CI level. Frontend implementation is now the active workstream.

## Backend verified
- Core authentication, tenant scoping, users/roles and password/session lifecycle.
- CRM customers, contacts and service locations.
- Equipment and service catalog.
- Agreements, acceptance, lifecycle transitions, immutable pricing snapshots, versions, audit events and renewals.
- Branches, business hours and closures.
- Maintenance schedules and work orders.
- Invoices, payments, refunds, credits, PDFs and CSV/reporting workflows.
- Recurring invoicing and billing worker.
- Email/SMS durable outboxes and workers.
- Attachments and S3-compatible storage integration.
- Signed webhooks with durable retries/dead-letter handling and domain events.
- Production configuration validation, CORS, migrations, concurrency checks and Docker Compose worker smoke tests.

## Backend verification evidence
Final documented GitHub Actions checkpoint:
- Run 244: SUCCESS.
- Ruff passed.
- PostgreSQL 16 migrations and Alembic drift checks passed.
- Full pytest suite passed.
- PostgreSQL concurrency tests passed.
- Docker Compose smoke passed for API, billing, maintenance, webhook, notification and SMS workers.

External provider/deployment verification is intentionally not claimed:
- Real SMTP delivery.
- Real SMS delivery.
- Real S3 delivery.
- Production deployment/TLS/secrets/monitoring.

## Frontend
Status: IN PROGRESS.

Planned implementation order:
1. Frontend foundation, authentication/session handling, routing and design system.
2. Dashboard and CRM/customer workflows.
3. Agreements and renewals.
4. Operations: work orders, maintenance, branches and technicians.
5. Billing: invoices, payments, refunds, credits and PDF download.
6. Equipment, catalog, users and company settings.
7. Attachments, imports, notifications, webhooks and reports where the backend contract supports a usable workflow.
8. End-to-end hardening, accessibility, responsive review and production build verification.

## API integration
The frontend will use the real backend at `VITE_API_URL` (default `http://localhost:8000`) and bearer authentication with the backend's access/refresh-token rotation.

## Current Git state
- Backend branch: `main`
- Frontend branch: `main`
- This file is the persistent recovery checkpoint for the combined project.

## Current next task
Build the frontend foundation and verify the first authenticated API flow against the existing backend contract.
