import hashlib
import hmac
import ipaddress
import json
import logging
import random
import socket
import time
from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from urllib.parse import urlsplit
from uuid import UUID

import httpx
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.core.webhook_crypto import decrypt_secret
from app.db.session import SessionLocal
from app.models import WebhookDelivery, WebhookDeliveryAttempt, WebhookEndpoint

logger = logging.getLogger(__name__)
SessionFactory = Callable[[], Session]
Sender = Callable[[WebhookEndpoint, WebhookDelivery], tuple[int, str]]


class WebhookDeliveryError(RuntimeError):
    pass


def validate_target(url: str) -> None:
    parsed = urlsplit(url)
    if parsed.scheme != "https" or not parsed.hostname:
        raise WebhookDeliveryError("Webhook target must use HTTPS")
    if parsed.username or parsed.password:
        raise WebhookDeliveryError("Webhook target must not embed credentials in the URL")
    if parsed.port not in (None, 443):
        raise WebhookDeliveryError("Webhook target must use the standard HTTPS port 443")
    try:
        addresses = {
            ipaddress.ip_address(result[4][0])
            for result in socket.getaddrinfo(
                parsed.hostname,
                parsed.port or 443,
                type=socket.SOCK_STREAM,
            )
        }
    except (OSError, ValueError) as exc:
        raise WebhookDeliveryError("Webhook target hostname could not be resolved") from exc
    if not addresses:
        raise WebhookDeliveryError("Webhook target hostname did not resolve to an address")
    for address in addresses:
        if not address.is_global:
            raise WebhookDeliveryError("Webhook target resolves to a non-public network address")


def render_payload(delivery: WebhookDelivery) -> bytes:
    envelope = {
        "id": str(delivery.event_id),
        "type": delivery.event_type,
        "created_at": delivery.created_at.astimezone(UTC).isoformat(),
        "data": delivery.payload,
    }
    return json.dumps(envelope, sort_keys=True, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def sign_payload(body: bytes, secret: str, timestamp: int) -> str:
    signed = f"{timestamp}.".encode() + body
    digest = hmac.new(secret.encode("utf-8"), signed, hashlib.sha256).hexdigest()
    return f"v1={digest}"


def send_webhook(endpoint: WebhookEndpoint, delivery: WebhookDelivery) -> tuple[int, str]:
    settings = get_settings()
    validate_target(endpoint.url)
    secret = decrypt_secret(endpoint.secret_ciphertext, settings.webhook_encryption_key)
    body = render_payload(delivery)
    timestamp = int(datetime.now(UTC).timestamp())
    headers = {
        "Content-Type": "application/json",
        "User-Agent": "Service-Agreement-Manager-Webhook/1.0",
        "X-SAM-Webhook-Id": str(delivery.event_id),
        "X-SAM-Webhook-Event": delivery.event_type,
        "X-SAM-Webhook-Timestamp": str(timestamp),
        "X-SAM-Webhook-Signature": sign_payload(body, secret, timestamp),
    }
    # Avoid ambient HTTP proxy settings and never buffer an unbounded response body.
    with httpx.Client(timeout=httpx.Timeout(10.0, read=3.0), follow_redirects=False, trust_env=False) as client:
        with client.stream("POST", endpoint.url, content=body, headers=headers) as response:
            response_status = response.status_code
            response_bytes = bytearray()
            deadline = time.monotonic() + 10.0
            for chunk in response.iter_bytes():
                remaining = 4000 - len(response_bytes)
                if remaining > 0:
                    response_bytes.extend(chunk[:remaining])
                if len(response_bytes) >= 4000 or time.monotonic() >= deadline:
                    break
            response_body = response_bytes.decode("utf-8", errors="replace")
    if not 200 <= response_status < 300:
        raise WebhookDeliveryError(
            f"Webhook endpoint returned HTTP {response_status}: {response_body}"
        )
    return response_status, response_body


def safe_error(exc: Exception) -> str:
    return f"{type(exc).__name__}: {exc}"[:1000]


def claim_due_deliveries(db: Session, *, batch_size: int = 10) -> list[tuple[UUID, UUID]]:
    now = datetime.now(UTC)
    lease_seconds = get_settings().webhook_lease_seconds
    stmt = select(WebhookDelivery).where(or_(
        and_(WebhookDelivery.status == "queued", WebhookDelivery.next_attempt_at <= now),
        and_(
            WebhookDelivery.status == "processing",
            WebhookDelivery.locked_until.is_not(None),
            WebhookDelivery.locked_until <= now,
        ),
    )).order_by(
        WebhookDelivery.next_attempt_at,
        WebhookDelivery.created_at,
    ).with_for_update(skip_locked=True).limit(batch_size)

    deliveries = list(db.scalars(stmt).all())
    claimed: list[tuple[UUID, UUID]] = []
    for delivery in deliveries:
        endpoint = db.get(WebhookEndpoint, delivery.endpoint_id)
        if endpoint is None or not endpoint.is_active:
            delivery.status = "cancelled"
            delivery.locked_until = None
            continue
        if delivery.status == "processing":
            previous = db.scalar(select(WebhookDeliveryAttempt).where(
                WebhookDeliveryAttempt.delivery_id == delivery.id,
                WebhookDeliveryAttempt.attempt_number == delivery.attempt_count,
            ))
            if previous is not None and previous.status == "started":
                previous.status = "failed"
                previous.error_message = "Worker lease expired; delivery outcome is unknown"
                previous.finished_at = now
        if delivery.attempt_count >= delivery.max_attempts:
            delivery.status = "dead"
            delivery.locked_until = None
            delivery.last_error = delivery.last_error or "Maximum delivery attempts reached"
            continue
        delivery.attempt_count += 1
        delivery.status = "processing"
        delivery.locked_until = now + timedelta(seconds=lease_seconds)
        attempt = WebhookDeliveryAttempt(
            delivery_id=delivery.id,
            attempt_number=delivery.attempt_count,
            status="started",
            started_at=now,
        )
        db.add(attempt)
        db.flush()
        claimed.append((delivery.id, attempt.id))
    db.commit()
    return claimed


def deliver_claimed(
    session_factory: SessionFactory,
    delivery_id: UUID,
    attempt_id: UUID,
    sender: Sender = send_webhook,
) -> None:
    db = session_factory()
    try:
        delivery = db.get(WebhookDelivery, delivery_id)
        attempt = db.get(WebhookDeliveryAttempt, attempt_id)
        endpoint = db.get(WebhookEndpoint, delivery.endpoint_id) if delivery else None
        if (
            delivery is None
            or attempt is None
            or endpoint is None
            or delivery.status != "processing"
            or attempt.status != "started"
        ):
            return
        db.expunge(delivery)
        db.expunge(endpoint)
    finally:
        db.close()

    try:
        http_status, response_body = sender(endpoint, delivery)
    except Exception as exc:
        now = datetime.now(UTC)
        error_text = safe_error(exc)
        db = session_factory()
        try:
            current = db.scalar(select(WebhookDelivery).where(
                WebhookDelivery.id == delivery_id
            ).with_for_update())
            attempt = db.get(WebhookDeliveryAttempt, attempt_id)
            endpoint = db.get(WebhookEndpoint, current.endpoint_id) if current else None
            if current is None or attempt is None or endpoint is None:
                return
            attempt.status = "failed"
            attempt.error_message = error_text
            attempt.finished_at = now
            current.last_error = error_text
            current.locked_until = None
            endpoint.last_delivery_at = now
            endpoint.last_delivery_status = "failed"
            if current.attempt_count >= current.max_attempts:
                current.status = "dead"
            else:
                backoff = min(3600, 30 * (2 ** (attempt.attempt_number - 1)))
                delay = max(1, int(backoff * random.uniform(0.8, 1.2)))
                current.status = "queued"
                current.next_attempt_at = now + timedelta(seconds=delay)
            db.commit()
        finally:
            db.close()
        return

    now = datetime.now(UTC)
    db = session_factory()
    try:
        current = db.scalar(select(WebhookDelivery).where(
            WebhookDelivery.id == delivery_id
        ).with_for_update())
        attempt = db.get(WebhookDeliveryAttempt, attempt_id)
        endpoint = db.get(WebhookEndpoint, current.endpoint_id) if current else None
        if current is None or attempt is None or endpoint is None:
            return
        current.status = "sent"
        current.delivered_at = now
        current.http_status = http_status
        current.response_body = response_body[:4000]
        current.locked_until = None
        current.last_error = None
        attempt.status = "sent"
        attempt.http_status = http_status
        attempt.response_body = response_body[:4000]
        attempt.finished_at = now
        endpoint.last_delivery_at = now
        endpoint.last_delivery_status = "sent"
        db.commit()
    finally:
        db.close()


def run_once(
    session_factory: SessionFactory = SessionLocal,
    *,
    sender: Sender = send_webhook,
    batch_size: int = 10,
) -> int:
    db = session_factory()
    try:
        claimed = claim_due_deliveries(db, batch_size=batch_size)
    finally:
        db.close()
    for delivery_id, attempt_id in claimed:
        deliver_claimed(session_factory, delivery_id, attempt_id, sender)
    return len(claimed)


def run_forever(poll_seconds: int | None = None) -> None:
    interval = poll_seconds or get_settings().webhook_poll_seconds
    while True:
        try:
            if run_once() == 0:
                time.sleep(interval)
        except KeyboardInterrupt:
            logger.info("Webhook worker shutting down")
            return
        except Exception:
            logger.exception("Webhook worker iteration failed")
            time.sleep(interval)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
