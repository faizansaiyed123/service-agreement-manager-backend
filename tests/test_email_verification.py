from urllib.parse import parse_qs, urlsplit

from conftest import TestingSession
from sqlalchemy import select

from app.api import auth as auth_api
from app.core.config import Settings
from app.models import EmailVerificationToken, NotificationOutbox, User


def production_signup_settings() -> Settings:
    return Settings(
        app_env="production",
        allow_public_registration=True,
        cors_origins=["http://localhost:3000"],
        email_verification_url="http://localhost:3000/verify-email",
        email_verification_token_minutes=60,
        email_verification_cooldown_seconds=60,
        smtp_host="smtp.example.com",
        smtp_from_email="no-reply@example.com",
    )


def verification_token_from_outbox(email: str) -> tuple[str, object]:
    db = TestingSession()
    try:
        record = db.scalar(select(NotificationOutbox).where(
            NotificationOutbox.event_type == "auth.email_verification",
            NotificationOutbox.recipient_email == email,
        ).order_by(NotificationOutbox.created_at.desc()))
        assert record is not None
        url_line = next(line for line in record.body.splitlines() if line.startswith("http"))
        token = parse_qs(urlsplit(url_line).fragment)["token"][0]
        return token, record.id
    finally:
        db.close()


def test_signup_requires_mailbox_owner_to_choose_final_password(client, monkeypatch):
    monkeypatch.setattr(auth_api, "get_settings", production_signup_settings)
    email = "verify-owner@example.com"
    registration_password = "attacker-chosen-password-123"
    final_owner_password = "mailbox-owner-password-456"
    origin = "http://localhost:3000"

    response = client.post(
        "/api/v1/auth/register",
        headers={"Origin": origin},
        json={
            "company_name": "Verification HVAC",
            "full_name": "New Owner",
            "email": email,
            "password": registration_password,
        },
    )
    assert response.status_code == 201, response.text
    assert response.json() == {"message": auth_api.REGISTRATION_MESSAGE}
    assert "access_token" not in response.text
    assert "refresh_token" not in response.text
    assert client.post("/api/v1/auth/login", headers={"Origin": origin}, json={
        "email": email, "password": registration_password,
    }).status_code == 403

    token, notification_id = verification_token_from_outbox(email)
    assert token not in response.text

    confirmed = client.post(
        "/api/v1/auth/verify-email",
        headers={"Origin": origin},
        json={"token": token, "new_password": final_owner_password},
    )
    assert confirmed.status_code == 204, confirmed.text

    replay = client.post(
        "/api/v1/auth/verify-email",
        headers={"Origin": origin},
        json={"token": token, "new_password": "replay-password-789"},
    )
    assert replay.status_code == 400

    original_password = client.post("/api/v1/auth/login", headers={"Origin": origin}, json={
        "email": email, "password": registration_password,
    })
    assert original_password.status_code == 401

    login = client.post("/api/v1/auth/login", headers={"Origin": origin}, json={
        "email": email, "password": final_owner_password,
    })
    assert login.status_code == 200, login.text
    assert login.json()["authenticated"] is True
    assert "access_token" not in login.json()
    assert "refresh_token" not in login.json()
    assert any("HttpOnly" in value for value in login.headers.get_list("set-cookie"))

    protected_notification = client.get(f"/api/v1/notifications/{notification_id}", headers={"Origin": origin})
    assert protected_notification.status_code == 404
    protected_attempts = client.get(f"/api/v1/notifications/{notification_id}/attempts", headers={"Origin": origin})
    assert protected_attempts.status_code == 404

    db = TestingSession()
    try:
        user = db.scalar(select(User).where(User.email == email))
        assert user is not None and user.email_verified is True
        assert db.scalar(select(EmailVerificationToken).where(
            EmailVerificationToken.token_hash.is_not(None),
            EmailVerificationToken.used_at.is_not(None),
        )) is not None
    finally:
        db.close()


def test_signup_response_does_not_reveal_existing_email(client, monkeypatch):
    monkeypatch.setattr(auth_api, "get_settings", production_signup_settings)
    origin = "http://localhost:3000"
    payload = {
        "company_name": "Duplicate Test HVAC",
        "full_name": "Duplicate Owner",
        "email": "duplicate-owner@example.com",
        "password": "correct-horse-battery-42",
    }
    first = client.post("/api/v1/auth/register", headers={"Origin": origin}, json=payload)
    second = client.post("/api/v1/auth/register", headers={"Origin": origin}, json=payload)
    assert first.status_code == second.status_code == 201
    assert first.json() == second.json() == {"message": auth_api.REGISTRATION_MESSAGE}


def test_verification_rejects_invalid_and_short_passwords(client, monkeypatch):
    monkeypatch.setattr(auth_api, "get_settings", production_signup_settings)
    origin = "http://localhost:3000"
    response = client.post("/api/v1/auth/verify-email", headers={"Origin": origin}, json={
        "token": "x" * 43,
        "new_password": "short",
    })
    assert response.status_code == 422
