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

### Verified frontend chunks so far
- Foundation committed on frontend `main`: typed API client with access-token injection and refresh-token retry, session storage, protected routes, responsive app shell, authentication screens, live overview dashboard and customer CRM workflow.
- Agreements: draft creation, propose/accept/activate/suspend/resume/cancel, acceptance evidence, version/event history and renewal offers.
- Operations: work-order creation, technician assignment, start/complete/cancel, maintenance schedules/generation and branches.
- Billing: invoice creation, issue/void, payments, refunds, credits, live balances and PDF download with idempotency keys.
- Equipment and service catalog CRUD entry points.
- Company/team/security settings and recurring-invoice controls.
- Reports, tenant-scoped CSV exports, password recovery, customer CSV preview/import, reusable attachment upload/download/delete, and email/SMS/webhook integration views.
- Frontend CI workflow added to run the production build on `main` pushes and pull requests.
- Local production build has not yet been independently executed because the environment has no GitHub/npm network access; the repository CI workflow is the source of remote build verification.

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

## Current verified frontend checkpoint
- Latest frontend `main` commit: `d913e0b90ea6537f88e15134be0e49b61393e12b`.
- Static source scan across 17 frontend TS/TSX modules found no brace/parenthesis/label mismatches, no triple-quote corruption, no dangling `React.FormEvent` usage, and no TODO/FIXME markers.
- Backend router audit confirmed frontend password recovery maps to the dedicated `/auth/forgot-password` and `/auth/reset-password` router.
- Customer contacts/service locations, branch business hours/closures, administrator password reset, recurring billing creation, attachment workflows, integrations and reports are all wired to live backend routes.

## Verification limitation
- Backend CI Run 244 is the verified application checkpoint.
- Frontend production build was not executable locally because npm dependencies are not installed and external package/network access is unavailable in this environment.
- The frontend GitHub Actions workflow exists, but the GitHub connector returned no workflow-run/status records for the verification commits; therefore frontend CI is **not claimed as passing**.
- A temporary CI-only PR (`#1`) was opened and closed after no status data became available; no product code was merged from that branch.

## Current next task
Perform external frontend CI/build verification (or run `npm install && npm run build` in an environment with package/network access), then deploy the frontend/backend with real secrets/providers if desired.
