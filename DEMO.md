# Service Agreement Manager — Demo API

This branch contains a **standalone in-memory demo backend** for recruiter demonstrations.

## Important

The production backend on `main` uses PostgreSQL, SQLAlchemy, authentication cookies, Redis-backed production controls, workers, storage and external provider integrations.

The demo backend deliberately does **not** use those systems.

It is implemented in:

```
app/demo/main.py
```

The process owns a deterministic in-memory dataset. Restarting the process resets all demo mutations.

## Run

From the repository root:

```bash
uvicorn app.demo.main:app --reload --port 8001
```

Useful endpoints:

- `/health/live`
- `/api/v1/auth/login`
- `/api/v1/auth/me`
- `/api/v1/customers`
- `/api/v1/agreements`
- `/api/v1/work-orders`
- `/api/v1/invoices`
- `/api/v1/equipment`
- `/api/v1/service-catalog`
- `/api/v1/reports/*`

## Why the frontend does not need this backend

The companion frontend `demo` branch contains its own browser-side demo adapter. That means a recruiter-facing frontend can be deployed by itself without deploying this API.

This backend exists so the project also has a real HTTP simulation that can be run locally when an API demonstration is useful.

## Verification

The demo-specific test can be run with:

```bash
pytest tests/test_demo_api.py
```

No production database is required for the demo test.
