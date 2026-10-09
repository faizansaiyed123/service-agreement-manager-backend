import logging
from contextlib import asynccontextmanager
from uuid import uuid4

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import text

from app.api import agreements, assets, auth, companies, customers, operations, users
from app.core.config import get_settings
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


app = FastAPI(title=settings.app_name, version="0.5.0", debug=settings.debug, lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
)
install_error_handlers(app)


@app.middleware("http")
async def request_context(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid4()))
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-ID"] = request_id
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
app.include_router(companies.router, prefix=settings.api_v1_prefix)
app.include_router(customers.router, prefix=settings.api_v1_prefix)
app.include_router(assets.equipment_router, prefix=settings.api_v1_prefix)
app.include_router(assets.catalog_router, prefix=settings.api_v1_prefix)
app.include_router(agreements.router, prefix=settings.api_v1_prefix)
app.include_router(users.router, prefix=settings.api_v1_prefix)
app.include_router(operations.schedules_router, prefix=settings.api_v1_prefix)
app.include_router(operations.work_orders_router, prefix=settings.api_v1_prefix)
