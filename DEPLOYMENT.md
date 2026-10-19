# Production deployment runbook

This runbook documents a single-host Docker Compose deployment. It does not provision a server, domain, SMTP account, or TLS certificate. A managed PostgreSQL service and managed object storage are preferable where available.

## 1. Prepare a secure host

Use a supported Linux host, restrict SSH, enable unattended security updates, and configure the host firewall. Expose only SSH and HTTPS; port 80 may be exposed for certificate issuance and redirects. PostgreSQL is intentionally not published to the host by the production Compose file. Put a TLS reverse proxy such as Caddy or Nginx in front of the API. The API is bound to 127.0.0.1 so it is reachable by a reverse proxy on the same host, not directly from the public internet.

## 2. Create production settings

Copy .env.production.example to .env.production and replace every placeholder before starting the services.

Generate independent cryptographically random values for JWT_SECRET_KEY (at least 48 characters) and WEBHOOK_ENCRYPTION_KEY (at least 32 characters). Use a URL-safe alphanumeric POSTGRES_PASSWORD because Compose inserts it into the database URL. Do not commit .env.production. Keep backups of secrets in an approved secrets manager; do not paste them into tickets or chat.

Set CORS_ORIGINS to the exact HTTPS frontend origin, without a trailing slash. Set PASSWORD_RESET_URL to the real frontend password-reset page. Configure working SMTP values: production startup intentionally fails if SMTP_HOST or SMTP_FROM_EMAIL is missing, or if STARTTLS is disabled. Set CORS_ORIGINS to an empty list only for a same-origin proxy deployment with no cross-origin frontend API requests.

For file uploads, local storage is persisted in the named attachments_data volume and is suitable only when one app instance shares that volume. Use the configured S3-compatible backend with HTTPS for horizontally scaled instances, and configure bucket access with a least-privilege identity. Arrange automated, encrypted backups and test restoration for the database and attachments before accepting real data.

## 3. Validate, build, and start

Run these commands from the backend repository root:

```sh
cp .env.production.example .env.production
# Edit .env.production and replace all placeholders first.
docker compose --env-file .env.production -f docker-compose.production.yml config
docker compose --env-file .env.production -f docker-compose.production.yml up --build -d
docker compose --env-file .env.production -f docker-compose.production.yml ps
docker compose --env-file .env.production -f docker-compose.production.yml logs --tail=200 api
```

The API container applies Alembic migrations before starting. This Compose file is intended for a single API instance; do not scale API replicas that run migrations on startup. For a multi-instance deployment, run migrations once as a release step and use a managed database or carefully designed shared storage. Keep database upgrades and application releases coordinated, and take a backup before migrations.

The standard workers for billing, webhooks, maintenance, and account notifications are started with this configuration. SMS delivery is optional. Configure SMS_PROVIDER=http and its HTTPS credentials in .env.production, then start the SMS profile:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml --profile sms up --build -d
```

## 4. Configure HTTPS reverse proxy

Terminate TLS at the host reverse proxy or hosting platform. Proxy requests to http://127.0.0.1:8000, preserve request method/body and the Authorization, Content-Type, Idempotency-Key, and X-Request-ID headers, and forward the original host/protocol as needed by your proxy. Configure the frontend domain separately and route frontend paths to the static app with an SPA fallback to index.html. Do not expose port 8000 or the database publicly.

## 5. Verify before opening access

```sh
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Also run the backend CI suite, frontend production build, and browser-based smoke tests against deployed URLs. Verify registration/login, token refresh/logout, password-reset email delivery, tenant isolation with two companies, attachments, invoice issue/payment/refund/credit calculations, CSV exports, webhook delivery, and worker restart behavior. Verify CORS rejects unconfigured origins, HTTP redirects to HTTPS at the edge, backups can be restored, and logs contain no secrets or access tokens. Health checks alone are not end-to-end validation.

## 6. Operational essentials

Monitor API and worker errors, database capacity and disk, queue retry/dead-letter growth, email delivery, and storage failures. Set backup retention and recovery-point/recovery-time targets, and keep a tested restore runbook. Rotate secrets with a planned rollout; rotate the webhook encryption key only with a migration/rotation plan for already encrypted webhook credentials. Keep a rollback image available, but understand that database migrations may not be reversible.
