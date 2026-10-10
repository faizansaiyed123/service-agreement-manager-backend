from datetime import UTC, datetime, timedelta
from uuid import UUID

from conftest import TestingSession
from sqlalchemy import select

from app.models import NotificationAttempt, NotificationOutbox
from app.workers.notifications import run_once


def register_owner(client, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Messaging HVAC", "full_name": "Messaging Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return response.json()


def body(schedule=None):
    data = {
        "event_type": "work_order.appointment_reminder",
        "recipient_email": "customer@example.com",
        "subject": "Upcoming maintenance appointment",
        "body": "Your annual maintenance is scheduled for tomorrow.",
        "payload": {"work_order_number": "WO-000007"},
    }
    if schedule:
        data["scheduled_at"] = schedule.isoformat()
    return data


def test_outbox_idempotency_tenant_isolation_and_successful_delivery(client):
    owner = register_owner(client, "notify-owner@example.com")
    other = register_owner(client, "notify-other@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    key_headers = {**headers, "Idempotency-Key": "notify-request-0001"}

    queued = client.post("/api/v1/notifications", headers=key_headers, json=body())
    assert queued.status_code == 201, queued.text
    notification_id = queued.json()["id"]
    assert queued.json()["status"] == "queued"

    replay = client.post("/api/v1/notifications", headers=key_headers, json=body())
    assert replay.status_code == 200
    assert replay.json()["id"] == notification_id
    changed = body()
    changed["subject"] = "Another subject"
    assert client.post("/api/v1/notifications", headers=key_headers, json=changed).status_code == 409
    assert client.get(f"/api/v1/notifications/{notification_id}", headers=other_headers).status_code == 404

    delivered = []
    def sender(notification):
        delivered.append(notification.id)
        return "<provider-message-1>"

    assert run_once(TestingSession, sender=sender) == 1
    assert delivered == [UUID(notification_id)]
    response = client.get(f"/api/v1/notifications/{notification_id}", headers=headers)
    assert response.status_code == 200
    assert response.json()["status"] == "sent"
    assert response.json()["attempt_count"] == 1
    assert response.json()["provider_message_id"] == "<provider-message-1>"
    attempts = client.get(f"/api/v1/notifications/{notification_id}/attempts", headers=headers)
    assert attempts.status_code == 200
    assert len(attempts.json()) == 1
    assert attempts.json()[0]["status"] == "sent"


def test_outbox_retry_exhaustion_and_manual_recovery(client):
    owner = register_owner(client, "notify-failure@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    created = client.post("/api/v1/notifications", headers={
        **headers, "Idempotency-Key": "notify-failure-0001",
    }, json=body())
    assert created.status_code == 201, created.text
    notification_id = UUID(created.json()["id"])

    for expected_attempt in range(1, 6):
        def failing_sender(_notification):
            raise RuntimeError("Temporary SMTP failure")
        assert run_once(TestingSession, sender=failing_sender) == 1
        db = TestingSession()
        try:
            record = db.get(NotificationOutbox, notification_id)
            assert record is not None
            assert record.attempt_count == expected_attempt
            if expected_attempt < 5:
                record.next_attempt_at = datetime.now(UTC) - timedelta(seconds=1)
            db.commit()
        finally:
            db.close()

    response = client.get(f"/api/v1/notifications/{notification_id}", headers=headers)
    assert response.json()["status"] == "dead"
    attempts = client.get(f"/api/v1/notifications/{notification_id}/attempts", headers=headers).json()
    assert len(attempts) == 5
    assert all(attempt["status"] == "failed" for attempt in attempts)

    retried = client.post(f"/api/v1/notifications/{notification_id}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "queued"
    assert retried.json()["max_attempts"] == 8
    assert run_once(TestingSession, sender=lambda _notification: "recovered-provider-id") == 1
    recovered = client.get(f"/api/v1/notifications/{notification_id}", headers=headers).json()
    assert recovered["status"] == "sent"
    assert recovered["attempt_count"] == 6

    db = TestingSession()
    try:
        history = list(db.scalars(select(NotificationAttempt).where(
            NotificationAttempt.notification_id == notification_id
        )).all())
        assert len(history) == 6
    finally:
        db.close()


def test_future_notifications_are_not_claimed(client):
    owner = register_owner(client, "notify-future@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    future = datetime.now(UTC) + timedelta(days=1)
    created = client.post("/api/v1/notifications", headers={
        **headers, "Idempotency-Key": "notify-future-0001",
    }, json=body(future))
    assert created.status_code == 201, created.text
    assert run_once(TestingSession, sender=lambda _notification: "should-not-send") == 0
    assert client.get(f"/api/v1/notifications/{created.json()['id']}", headers=headers).json()["status"] == "queued"
