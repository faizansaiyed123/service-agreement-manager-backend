# Production deployment runbook

This runbook documents a single-host Docker Compose deployment. It does not provision a server, domain, SMTP account, or TLS certificate. A managed PostgreSQL service and managed object storage are preferable where available.

## 1. Prepare a secure host

Use a supported Linux host, restrict SSH, enable unattended security updates, and configure the host firewall. Expose only SSH and HTTPS; port 80 may be exposed for certificate issuance and redirects. PostgreSQL is intentionally not published to the host by the production Compose file. Put a TLS reverse proxy such as Caddy or Nginx in front of the API. The API is bound to 127.0.0.1 so it is reachable by a reverse proxy on the same host, not directly from the public internet.

## 2. Create production settings

Copy .env.production.example to .env.production and replace every placeholder before starting the services.

Generate independent cryptographically random values for JWT_SECRET_KEY (at least 48 characters) and WEBHOOK_ENCRYPTION_KEY (at least 32 characters). Use a URL-safe alphanumeric POSTGRES_PASSWORD because Compose inserts it into the database URL. Do not commit .env.production. Keep backups of secrets in an approved secrets manager; do not paste them into tickets or chat.

Set CORS_ORIGINS to the exact public HTTPS app origin, without a trailing slash. It is also the server-side trusted Origin allowlist for cookie-session CSRF protection, so it must not be empty in production, even for the recommended same-origin proxy setup. Set COOKIE_SAMESITE=lax for same-origin or same-site deployments. Set PASSWORD_RESET_URL and EMAIL_VERIFICATION_URL to real frontend pages on that same HTTPS origin. Keep ALLOW_PUBLIC_REGISTRATION=true only if email verification and delivery are ready; signup remains pending until the recipient opens the single-use link and sets their own final password. Configure working SMTP values: production startup intentionally fails if SMTP_HOST or SMTP_FROM_EMAIL is missing, or if STARTTLS is disabled.

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

The API container applies Alembic migrations before starting. In the production registration flow, a new workspace owner must verify control of the submitted email and choose the final password through the single-use link. Confirm the delivery worker is running and SMTP is configured before enabling public signup. For a private beta, set `ALLOW_PUBLIC_REGISTRATION=false` and build the frontend with `--build-arg VITE_PUBLIC_REGISTRATION=false`.

An operator can alternatively bootstrap a trusted first owner after the API is healthy:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml exec api python -m app.cli create-owner
```

Use an email address you control and enter the password at the hidden prompt; do not put it on the command line.

This Compose file is intended for a single API instance; do not scale API replicas that run migrations on startup. For a multi-instance deployment, run migrations once as a release step and use a managed database or carefully designed shared storage. Keep database upgrades and application releases coordinated, and take a backup before migrations.

The standard workers for billing, webhooks, maintenance, and account notifications are started with this configuration. SMS delivery is optional. Configure SMS_PROVIDER=http and its HTTPS credentials in .env.production, then start the SMS profile:

```sh
docker compose --env-file .env.production -f docker-compose.production.yml --profile sms up --build -d
```

## 4. Configure HTTPS reverse proxy

Terminate TLS at the host reverse proxy or hosting platform. Proxy requests to http://127.0.0.1:8000, preserve request method/body and the Cookie, Set-Cookie, Origin, Authorization, Content-Type, Idempotency-Key, and X-Request-ID headers, and forward the original host/protocol as needed by your proxy. Configure the frontend domain separately and route frontend paths to the static app with an SPA fallback to index.html. Do not expose port 8000 or the database publicly.

## 5. Put the frontend and API behind HTTPS on one origin

For a simple single-host setup, build the frontend container from the frontend repository with the default empty `VITE_API_URL`, then bind its Nginx port to loopback:

```sh
# Run from the frontend repository, on the same host as this backend.
docker build -t service-agreement-manager-frontend .
docker run -d --name sam-frontend --restart unless-stopped \
  -p 127.0.0.1:8080:80 service-agreement-manager-frontend
```

Install Caddy on the host and configure a site for your real domain (replace `app.example.com`). Caddy obtains/renews TLS certificates if DNS points to the host and ports 80/443 are reachable:

```caddyfile
app.example.com {
    encode zstd gzip
    header Strict-Transport-Security "max-age=31536000"

    @api path /api/v1/*
    handle @api {
        reverse_proxy 127.0.0.1:8000
    }

    @health path /health/*
    handle @health {
        reverse_proxy 127.0.0.1:8000
    }

    handle {
        reverse_proxy 127.0.0.1:8080
    }
}
```

For this same-origin setup, set `PASSWORD_RESET_URL=https://app.example.com/reset-password`. Configure `CORS_ORIGINS=https://app.example.com` even though the browser calls the API on the same origin: the backend uses this exact allowlist to reject untrusted request origins. Keep `COOKIE_SAMESITE=lax`. The app will call relative `/api/v1` paths. The proxy deliberately does not expose the interactive API docs at `/docs` publicly.

A separate API hostname is possible when both names are same-site (for example, `app.example.com` and `api.example.com`): set `VITE_API_URL=https://api.example.com`, `CORS_ORIGINS=https://app.example.com`, and `PASSWORD_RESET_URL` to the frontend page. Update the frontend CSP `connect-src` directive to include that exact API origin. For unrelated frontend/API sites, cookies require `COOKIE_SAMESITE=none` and Secure; browser third-party-cookie restrictions can still block them, so same-origin deployment is strongly preferred. Never expose tokens or credentials through frontend build variables.

## 6. Verify before opening access

```sh
curl --fail http://127.0.0.1:8000/health/live
curl --fail http://127.0.0.1:8000/health/ready
docker compose --env-file .env.production -f docker-compose.production.yml ps
```

Also run the backend CI suite, frontend production build, and browser-based smoke tests against deployed URLs. Verify email-verified signup and final password setup, owner bootstrap/login, token refresh/logout, password-reset email delivery, tenant isolation with two companies, attachments, invoice issue/payment/refund/credit calculations, CSV exports, webhook delivery, and worker restart behavior. Verify CORS rejects unconfigured origins, HTTP redirects to HTTPS at the edge, backups can be restored, and logs contain no secrets or access tokens. Health checks alone are not end-to-end validation.

## 7. Abuse protection at the edge

The application now applies sliding-window limits to login (per IP and account identifier), registration, password-reset requests, and reset confirmations. These counters are process-local, reset on restart, and are not shared across replicas; they are defense in depth, not a complete distributed abuse control. Before public launch, enable provider-level WAF/rate-limiting rules for `/api/v1/auth/login`, `/api/v1/auth/register`, `/api/v1/auth/forgot-password`, and `/api/v1/auth/reset-password`, and monitor repeated 401/429 responses and registration spikes. If the service later runs multiple API replicas, use a shared rate-limit store. Do not rely on CORS as an abuse control.

## 8. Operational essentials

Monitor API and worker errors, database capacity and disk, queue retry/dead-letter growth, email delivery, and storage failures. Set backup retention and recovery-point/recovery-time targets, and keep a tested restore runbook. Rotate secrets with a planned rollout; rotate the webhook encryption key only with a migration/rotation plan for already encrypted webhook credentials. Keep a rollback image available, but understand that database migrations may not be reversible.
