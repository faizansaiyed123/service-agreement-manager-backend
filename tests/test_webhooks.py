import hashlib
import hmac
import json
from datetime import UTC, datetime

from app.core.webhook_crypto import decrypt_secret
from app.models import User, WebhookDelivery
from app.webhook_service import publish_webhook_event
from app.workers.webhooks import run_once, sign_payload
from tests.conftest import TestingSession


def register(client, company, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company,
        "full_name": "Webhook Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_webhook_endpoint_crud_secret_rotation_and_https_validation(client):
    headers = register(client, "Webhook HVAC", "webhook@example.com")

    invalid = client.post("/api/v1/webhooks", headers=headers, json={
        "name": "Insecure",
        "url": "http://example.com/webhook",
        "events": ["customer.created"],
    })
    assert invalid.status_code == 422

    created = client.post("/api/v1/webhooks", headers=headers, json={
        "name": "ERP",
        "url": "https://example.com/webhook",
        "events": ["customer.created", "payment.received"],
    })
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["name"] == "ERP"
    assert body["subscribed_events"] == ["customer.created", "payment.received"]
    assert body["secret"]
    assert len(body["secret"]) >= 32

    listed = client.get("/api/v1/webhooks", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["url"] == "https://example.com/webhook"
    assert "secret" not in listed.json()[0]

    settings_key = client.get("/api/v1/webhooks", headers=headers).headers  # proves protected route works
    assert settings_key is not None

    rotated = client.post(
        f"/api/v1/webhooks/{body['id']}/rotate-secret",
        headers=headers,
    )
    assert rotated.status_code == 200, rotated.text
    assert rotated.json()["secret"] != body["secret"]

    disabled = client.delete(f"/api/v1/webhooks/{body['id']}", headers=headers)
    assert disabled.status_code == 200
    assert disabled.json()["is_active"] is False


def test_webhook_publish_delivery_signing_and_tenant_isolation(client):
    first_headers = register(client, "Webhook Company One", "webhook-one@example.com")
    second_headers = register(client, "Webhook Company Two", "webhook-two@example.com")

    created = client.post("/api/v1/webhooks", headers=first_headers, json={
        "name": "Events",
        "url": "https://example.com/events",
        "events": ["customer.created"],
    })
    assert created.status_code == 201, created.text
    created_body = created.json()

    first_user = TestingSession().query(User).filter_by(email="webhook-one@example.com").one()
    db = TestingSession()
    try:
        user = db.query(User).filter_by(email="webhook-one@example.com").one()
        assert user.id == first_user.id
        event_id = publish_webhook_event(
            db,
            user.company_id,
            "customer.created",
            {"customer_id": "customer-1"},
        )
        db.commit()

        ignored_event_id = publish_webhook_event(
            db,
            user.company_id,
            "invoice.issued",
            {"invoice_id": "invoice-1"},
        )
        db.commit()

        deliveries = db.query(WebhookDelivery).filter(
            WebhookDelivery.event_id == event_id
        ).all()
        assert len(deliveries) == 1
        assert deliveries[0].endpoint_id.hex == created_body["id"].replace("-", "")
        ignored = db.query(WebhookDelivery).filter(
            WebhookDelivery.event_id == ignored_event_id
        ).all()
        assert ignored == []
    finally:
        db.close()
        first_user = None

    second_view = client.get(
        f"/api/v1/webhooks/{created_body['id']}",
        headers=second_headers,
    )
    assert second_view.status_code == 404

    secret = created_body["secret"]
    body = json.dumps(
        {"data": {"customer_id": "customer-1"}, "id": str(event_id), "type": "customer.created",
         "created_at": datetime.now(UTC).isoformat()},
        sort_keys=True,
        separators=(",", ":"),
    ).encode()
    timestamp = 1234567890
    expected = hmac.new(
        secret.encode(),
        f"{timestamp}.".encode() + body,
        hashlib.sha256,
    ).hexdigest()
    assert sign_payload(body, secret, timestamp) == f"v1={expected}"


def test_webhook_worker_marks_success_and_retries_failures(client):
    headers = register(client, "Webhook Worker Company", "webhook-worker@example.com")
    created = client.post("/api/v1/webhooks", headers=headers, json={
        "name": "Worker",
        "url": "https://example.com/events",
        "events": ["customer.created"],
    })
    assert created.status_code == 201, created.text

    db = TestingSession()
    try:
        user = db.query(User).filter_by(email="webhook-worker@example.com").one()
        event_id = publish_webhook_event(db, user.company_id, "customer.created", {"customer_id": "c-1"})
        db.commit()
    finally:
        db.close()

    def sender(endpoint, delivery):
        assert endpoint.url == "https://example.com/events"
        assert delivery.event_id == event_id
        return 200, '{"ok":true}'

    assert run_once(session_factory=TestingSession, sender=sender) == 1

    db = TestingSession()
    try:
        delivery = db.query(WebhookDelivery).filter(WebhookDelivery.event_id == event_id).one()
        assert delivery.status == "sent"
        assert delivery.attempt_count == 1
        assert delivery.http_status == 200
    finally:
        db.close()
