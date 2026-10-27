import secrets
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.webhook_crypto import encrypt_secret
from app.db.session import get_db
from app.models import User, WebhookDelivery, WebhookDeliveryAttempt, WebhookEndpoint
from app.schemas.webhooks import (
    WebhookDeliveryAttemptRead,
    WebhookDeliveryRead,
    WebhookEndpointCreated,
    WebhookEndpointCreate,
    WebhookEndpointRead,
    WebhookEndpointUpdate,
)

router = APIRouter(prefix="/webhooks", tags=["webhooks"])
MANAGER_ROLES = ("owner", "admin", "manager")


def scoped_endpoint(db: Session, company_id: UUID, endpoint_id: UUID) -> WebhookEndpoint:
    endpoint = db.scalar(select(WebhookEndpoint).where(
        WebhookEndpoint.id == endpoint_id,
        WebhookEndpoint.company_id == company_id,
    ))
    if endpoint is None:
        raise DomainError(404, "webhook_endpoint_not_found", "Webhook endpoint not found")
    return endpoint


def scoped_delivery(db: Session, company_id: UUID, delivery_id: UUID) -> WebhookDelivery:
    delivery = db.scalar(select(WebhookDelivery).where(
        WebhookDelivery.id == delivery_id,
        WebhookDelivery.company_id == company_id,
    ))
    if delivery is None:
        raise DomainError(404, "webhook_delivery_not_found", "Webhook delivery not found")
    return delivery


def new_secret() -> str:
    return secrets.token_urlsafe(32)


@router.post("", response_model=WebhookEndpointCreated, status_code=201)
def create_endpoint(
    payload: WebhookEndpointCreate,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    secret = new_secret()
    endpoint = WebhookEndpoint(
        company_id=user.company_id,
        created_by_user_id=user.id,
        name=payload.name,
        url=str(payload.url),
        secret_ciphertext=encrypt_secret(secret, get_settings().webhook_encryption_key),
        subscribed_events=payload.events,
        is_active=payload.is_active,
    )
    db.add(endpoint)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "webhook_endpoint_conflict", "A webhook endpoint with this name already exists") from exc
    db.refresh(endpoint)
    return {
        **WebhookEndpointRead.model_validate(endpoint).model_dump(),
        "secret": secret,
    }


@router.get("", response_model=list[WebhookEndpointRead])
def list_endpoints(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebhookEndpoint]:
    return list(db.scalars(select(WebhookEndpoint).where(
        WebhookEndpoint.company_id == user.company_id,
    ).order_by(WebhookEndpoint.created_at.desc(), WebhookEndpoint.id)).all())


@router.get("/{endpoint_id}", response_model=WebhookEndpointRead)
def get_endpoint(
    endpoint_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebhookEndpoint:
    return scoped_endpoint(db, user.company_id, endpoint_id)


@router.patch("/{endpoint_id}", response_model=WebhookEndpointRead)
def update_endpoint(
    endpoint_id: UUID,
    payload: WebhookEndpointUpdate,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> WebhookEndpoint:
    endpoint = scoped_endpoint(db, user.company_id, endpoint_id)
    changes = payload.model_dump(exclude_unset=True)
    if "name" in changes:
        endpoint.name = changes["name"]
    if "url" in changes:
        endpoint.url = str(changes["url"])
    if "events" in changes:
        endpoint.subscribed_events = changes["events"]
    if "is_active" in changes:
        endpoint.is_active = changes["is_active"]
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise DomainError(409, "webhook_endpoint_conflict", "Webhook endpoint name conflicts with another endpoint") from exc
    db.refresh(endpoint)
    return endpoint


@router.post("/{endpoint_id}/rotate-secret", response_model=WebhookEndpointCreated)
def rotate_secret(
    endpoint_id: UUID,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> dict:
    endpoint = scoped_endpoint(db, user.company_id, endpoint_id)
    secret = new_secret()
    endpoint.secret_ciphertext = encrypt_secret(secret, get_settings().webhook_encryption_key)
    endpoint.is_active = True
    db.commit()
    db.refresh(endpoint)
    return {
        **WebhookEndpointRead.model_validate(endpoint).model_dump(),
        "secret": secret,
    }


@router.delete("/{endpoint_id}", response_model=WebhookEndpointRead)
def deactivate_endpoint(
    endpoint_id: UUID,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> WebhookEndpoint:
    endpoint = scoped_endpoint(db, user.company_id, endpoint_id)
    endpoint.is_active = False
    db.commit()
    db.refresh(endpoint)
    return endpoint


@router.get("/{endpoint_id}/deliveries", response_model=list[WebhookDeliveryRead])
def list_endpoint_deliveries(
    endpoint_id: UUID,
    status: str | None = Query(default=None, pattern="^(queued|processing|sent|dead|cancelled)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebhookDelivery]:
    endpoint = scoped_endpoint(db, user.company_id, endpoint_id)
    stmt = select(WebhookDelivery).where(WebhookDelivery.endpoint_id == endpoint.id)
    if status:
        stmt = stmt.where(WebhookDelivery.status == status)
    return list(db.scalars(
        stmt.order_by(WebhookDelivery.created_at.desc(), WebhookDelivery.id).limit(limit).offset(offset)
    ).all())


@router.get("/deliveries/{delivery_id}", response_model=WebhookDeliveryRead)
def get_delivery(
    delivery_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WebhookDelivery:
    return scoped_delivery(db, user.company_id, delivery_id)


@router.get("/deliveries/{delivery_id}/attempts", response_model=list[WebhookDeliveryAttemptRead])
def list_delivery_attempts(
    delivery_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[WebhookDeliveryAttempt]:
    delivery = scoped_delivery(db, user.company_id, delivery_id)
    return list(db.scalars(select(WebhookDeliveryAttempt).where(
        WebhookDeliveryAttempt.delivery_id == delivery.id,
    ).order_by(WebhookDeliveryAttempt.attempt_number)).all())


@router.post("/deliveries/{delivery_id}/retry", response_model=WebhookDeliveryRead)
def retry_delivery(
    delivery_id: UUID,
    response: Response,
    user: User = Depends(require_roles(*MANAGER_ROLES)),
    db: Session = Depends(get_db),
) -> WebhookDelivery:
    delivery = db.scalar(select(WebhookDelivery).where(
        WebhookDelivery.id == delivery_id,
        WebhookDelivery.company_id == user.company_id,
    ).with_for_update())
    if delivery is None:
        raise DomainError(404, "webhook_delivery_not_found", "Webhook delivery not found")
    if delivery.status != "dead":
        raise DomainError(409, "webhook_delivery_not_dead", "Only dead webhook deliveries can be retried")
    if delivery.attempt_count >= 20:
        raise DomainError(409, "webhook_retry_limit", "Maximum webhook delivery attempts have been reached")
    delivery.max_attempts = min(20, max(delivery.max_attempts, delivery.attempt_count + 2))
    delivery.status = "queued"
    delivery.next_attempt_at = datetime.now(UTC)
    delivery.locked_until = None
    response.status_code = 200
    db.commit()
    db.refresh(delivery)
    return delivery
