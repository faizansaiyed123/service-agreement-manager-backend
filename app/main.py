import logging
from contextlib import asynccontextmanager
from uuid import UUID, uuid4

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import agreements, assets, attachments, auth, billing, branches, companies, customer_imports, customers, exports, notifications, operations, password_recovery, reports, renewals, recurring_invoices, sms, users, webhooks
from app.core.config import get_settings
from app.core.auth_cookies import ACCESS_COOKIE, REFRESH_COOKIE
from app.core.errors import install_error_handlers
from app.db.session import engine

settings = get_settings()
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)s %(name)s %(message)s",
)


@asynccontextmanager
async def lifespan(_: FastAPI):
    yield
    engine.dispose()


app = FastAPI(title=settings.app_name, version="0.6.0", debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "Idempotency-Key", "X-Request-ID"],
    expose_headers=["X-Request-ID", "X-Attachment-SHA256"],
)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    candidate_request_id = request.headers.get("X-Request-ID", "")
    try:
        request_id = str(UUID(candidate_request_id))
    except (ValueError, TypeError, AttributeError):
        request_id = str(uuid4())
    request.state.request_id = request_id

    def rejected(code: str, message: str) -> JSONResponse:
        response = JSONResponse(
            status_code=403,
            content={"error": {"code": code, "message": message}},
        )
        response.headers["X-Request-ID"] = request_id
        response.headers["Cache-Control"] = "no-store"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        return response

    allowed_origins = {origin.rstrip("/") for origin in settings.cors_origins}
    origin = request.headers.get("origin")
    if origin and origin.rstrip("/") not in allowed_origins:
        return rejected("origin_not_allowed", "Request origin is not allowed")

    public_auth_paths = {
        f"{settings.api_v1_prefix.rstrip('/')}/auth/login",
        f"{settings.api_v1_prefix.rstrip('/')}/auth/register",
        f"{settings.api_v1_prefix.rstrip('/')}/auth/forgot-password",
        f"{settings.api_v1_prefix.rstrip('/')}/auth/reset-password",
        f"{settings.api_v1_prefix.rstrip('/')}/auth/verify-email",
        f"{settings.api_v1_prefix.rstrip('/')}/auth/resend-verification",
    }
    if request.method not in {"GET", "HEAD", "OPTIONS"} and request.url.path not in public_auth_paths:
        has_session_cookie = bool(request.cookies.get(ACCESS_COOKIE) or request.cookies.get(REFRESH_COOKIE))
        if has_session_cookie and (not origin or origin.rstrip("/") not in allowed_origins):
            return rejected("csrf_origin_required", "A trusted Origin header is required")

    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    return response


@app.get("/health/live", tags=["health"])
def liveness() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready", tags=["health"])
def readiness() -> dict[str, str]:
    with engine.connect() as connection:
        connection.execute(text("SELECT 1"))
    return {"status": "ready"}


@app.get("/", include_in_schema=False)
def root() -> dict[str, str]:
    return {"name": settings.app_name, "docs": "/docs"}


app.include_router(auth.router, prefix=settings.api_v1_prefix)
app.include_router(branches.router, prefix=settings.api_v1_prefix)
app.include_router(password_recovery.router, prefix=settings.api_v1_prefix)
app.include_router(companies.router, prefix=settings.api_v1_prefix)
app.include_router(customer_imports.router, prefix=settings.api_v1_prefix)
app.include_router(attachments.router, prefix=settings.api_v1_prefix)
app.include_router(webhooks.router, prefix=settings.api_v1_prefix)
app.include_router(recurring_invoices.router, prefix=settings.api_v1_prefix)
app.include_router(sms.router, prefix=settings.api_v1_prefix)
app.include_router(customers.router, prefix=settings.api_v1_prefix)
app.include_router(assets.equipment_router, prefix=settings.api_v1_prefix)
app.include_router(assets.catalog_router, prefix=settings.api_v1_prefix)
app.include_router(agreements.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(operations.schedules_router, prefix=settings.api_v1_prefix)
app.include_router(operations.work_orders_router, prefix=settings.api_v1_prefix)
app.include_router(billing.router, prefix=settings.api_v1_prefix)
app.include_router(renewals.router, prefix=settings.api_v1_prefix)
app.include_router(notifications.router, prefix=settings.api_v1_prefix)
app.include_router(reports.router, prefix=settings.api_v1_prefix)
app.include_router(exports.router, prefix=settings.api_v1_prefix)
