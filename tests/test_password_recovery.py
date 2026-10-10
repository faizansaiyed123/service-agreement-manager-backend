from datetime import UTC, datetime, timedelta
from urllib.parse import parse_qs, urlsplit
from uuid import UUID

from conftest import TestingSession
from sqlalchemy import func, select

from app.models import NotificationOutbox, PasswordResetToken


def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Recovery HVAC",
        "full_name": "Recovery Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return response.json()


def request_reset(client, email):
    return client.post("/api/v1/auth/forgot-password", json={"email": email})


def recover_token_from_outbox(email):
    db = TestingSession()
    try:
        record = db.scalar(select(NotificationOutbox).where(
            NotificationOutbox.event_type == "auth.password_reset",
            NotificationOutbox.recipient_email == email,
        ).order_by(NotificationOutbox.created_at.desc()))
        assert record is not None
        url_line = next(line for line in record.body.splitlines() if line.startswith("http"))
        values = parse_qs(urlsplit(url_line).query)
        return values["token"][0], record.id
    finally:
        db.close()


def test_recovery_response_is_generic_and_reset_invalidates_all_sessions(client):
    email = "recovery-owner@example.com"
    unknown = request_reset(client, "not-registered@example.com")
    registered = register(client, email)
    first_headers = {"Authorization": f"Bearer {registered['access_token']}"}
    second_login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "correct-horse-battery-42",
    })
    assert second_login.status_code == 200, second_login.text
    second = second_login.json()
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}

    requested = request_reset(client, email)
    assert unknown.status_code == requested.status_code == 202
    assert unknown.json() == requested.json()
    assert "token" not in requested.text.lower()
    assert "exists" in requested.json()["message"].lower()

    token, notification_id = recover_token_from_outbox(email)
    assert token not in requested.text
    # Cooldown suppresses duplicate messages without changing the public response.
    duplicate = request_reset(client, email)
    assert duplicate.status_code == 202
    assert duplicate.json() == requested.json()
    db = TestingSession()
    try:
        assert db.scalar(select(func.count()).select_from(PasswordResetToken)) == 1
        assert db.scalar(select(func.count()).select_from(NotificationOutbox).where(
            NotificationOutbox.event_type == "auth.password_reset"
        )) == 1
    finally:
        db.close()

    # Outbox reads must never reveal the secret reset URL, even to another user
    # in the same company who can otherwise read ordinary notification records.
    assert client.get("/api/v1/notifications?event_type=auth.password_reset", headers=first_headers).json() == []
    assert client.get(f"/api/v1/notifications/{notification_id}", headers=first_headers).status_code == 404
    assert client.get(f"/api/v1/notifications/{notification_id}/attempts", headers=first_headers).status_code == 404

    reset = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "new-correct-horse-battery-43",
    })
    assert reset.status_code == 204, reset.text
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second_headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": registered["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": second["refresh_token"]}).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": email, "password": "correct-horse-battery-42",
    }).status_code == 401
    new_login = client.post("/api/v1/auth/login", json={
        "email": email, "password": "new-correct-horse-battery-43",
    })
    assert new_login.status_code == 200, new_login.text

    replay = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "another-correct-horse-battery-44",
    })
    assert replay.status_code == 400


def test_recovery_rejects_expired_or_unknown_tokens(client):
    email = "recovery-expired@example.com"
    register(client, email)
    assert request_reset(client, email).status_code == 202
    token, _ = recover_token_from_outbox(email)

    db = TestingSession()
    try:
        item = db.scalar(select(PasswordResetToken).where(
            PasswordResetToken.token_hash.is_not(None)
        ))
        assert item is not None
        item.expires_at = datetime.now(UTC) - timedelta(seconds=1)
        db.commit()
    finally:
        db.close()

    expired = client.post("/api/v1/auth/reset-password", json={
        "token": token, "new_password": "a-new-strong-password-45",
    })
    assert expired.status_code == 400
    unknown = client.post("/api/v1/auth/reset-password", json={
        "token": "x" * 43, "new_password": "a-new-strong-password-45",
    })
    assert unknown.status_code == 400
    assert unknown.json() == expired.json()


def test_recovery_input_validation(client):
    assert client.post("/api/v1/auth/forgot-password", json={"email": "not-an-email"}).status_code == 422
    short_token = client.post("/api/v1/auth/reset-password", json={
        "token": "too-short", "new_password": "a-new-strong-password-45",
    })
    assert short_token.status_code == 422
    short_password = client.post("/api/v1/auth/reset-password", json={
        "token": "x" * 43, "new_password": "short",
    })
    assert short_password.status_code == 422
