# API testing

Copy .env.example to .env, replace the sample JWT secret and run docker compose up --build -d. Swagger UI is at /docs.

1. Register with POST /api/v1/auth/register using company_name, full_name, email and a password of at least 12 characters.
2. Sign in with POST /api/v1/auth/login.
3. Set the returned access_token as Authorization: Bearer <token>.
4. Inspect the authenticated profile with GET /api/v1/auth/me.
5. Create and query customers under /api/v1/customers.
6. Add contacts and service locations through the nested customer endpoints.
7. Register a second company and verify its token gets 404 when attempting to read the first company's customer ID.

Tests in tests/ provide repeatable request examples. Do not put real customer data or credentials into test fixtures or issue reports.
