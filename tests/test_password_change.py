from app.core.security import verify_password
from app.models import AuthSession, User
from conftest import TestingSession
from sqlalchemy import select


def register(client):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Account Security HVAC",
        "full_name": "Account Owner",
        "email": "password-change@example.com",
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_password_change_invalidates_all_sessions_and_refresh_tokens(client):
    first_session = register(client)
    login = client.post("/api/v1/auth/login", json={
        "email": "password-change@example.com",
        "password": "correct-horse-battery-42",
    })
    assert login.status_code == 200, login.text

    first_headers = {"Authorization": f"Bearer {first_session['access_token']}"}
    second_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    invalid = client.post("/api/v1/auth/change-password", headers=first_headers, json={
        "current_password": "wrong-password",
        "new_password": "new-secure-password-987",
    })
    assert invalid.status_code == 401
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 200

    unchanged = client.post("/api/v1/auth/change-password", headers=first_headers, json={
        "current_password": "correct-horse-battery-42",
        "new_password": "correct-horse-battery-42",
    })
    assert unchanged.status_code == 409

    changed = client.post("/api/v1/auth/change-password", headers=first_headers, json={
        "current_password": "correct-horse-battery-42",
        "new_password": "new-secure-password-987",
    })
    assert changed.status_code == 204
    assert client.get("/api/v1/auth/me", headers=first_headers).status_code == 401
    assert client.get("/api/v1/auth/me", headers=second_headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={
        "refresh_token": first_session["refresh_token"],
    }).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={
        "refresh_token": login.json()["refresh_token"],
    }).status_code == 401
    assert client.post("/api/v1/auth/login", json={
        "email": "password-change@example.com",
        "password": "correct-horse-battery-42",
    }).status_code == 401

    new_login = client.post("/api/v1/auth/login", json={
        "email": "password-change@example.com",
        "password": "new-secure-password-987",
    })
    assert new_login.status_code == 200, new_login.text


def test_password_change_persists_only_a_hash(client):
    session_data = register(client)
    headers = {"Authorization": f"Bearer {session_data['access_token']}"}
    response = client.post("/api/v1/auth/change-password", headers=headers, json={
        "current_password": "correct-horse-battery-42",
        "new_password": "new-secure-password-987",
    })
    assert response.status_code == 204
    db = TestingSession()
    try:
        user = db.scalar(select(User).where(User.email == "password-change@example.com"))
        assert user is not None
        assert user.password_hash != "new-secure-password-987"
        assert verify_password("new-secure-password-987", user.password_hash)
        sessions = list(db.scalars(select(AuthSession).where(AuthSession.user_id == user.id)).all())
        assert sessions
        assert all(session.revoked_at is not None for session in sessions)
    finally:
        db.close()
