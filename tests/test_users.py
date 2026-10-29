def register(client, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Workforce HVAC", "full_name": "Company Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_user_admin_tenant_scope_and_logout_revocation(client):
    first = register(client, "workforce@example.com")
    other = register(client, "other-workforce@example.com")
    headers = {"Authorization": f"Bearer {first['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    created = client.post("/api/v1/users", headers=headers, json={
        "full_name": "Field Technician", "email": "tech@example.com",
        "password": "technician-password-42", "role": "staff",
    })
    assert created.status_code == 201, created.text
    tech_id = created.json()["id"]
    assert created.json()["role"] == "staff"
    assert client.get("/api/v1/users", headers=headers).status_code == 200
    assert client.get(f"/api/v1/users/{tech_id}", headers=other_headers).status_code == 404
    assert client.post("/api/v1/users", headers=other_headers, json={
        "full_name": "Duplicate Scope", "email": "tech@example.com",
        "password": "technician-password-43", "role": "staff",
    }).status_code == 409
    assert client.post("/api/v1/auth/logout", headers=headers).status_code == 204
    assert client.get("/api/v1/auth/me", headers=headers).status_code == 401
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": first["refresh_token"]}).status_code == 401


def test_deactivating_user_revokes_active_access_and_refresh_sessions(client):
    owner = register(client, "session-admin@example.com")
    owner_headers = {"Authorization": f"Bearer {owner['access_token']}"}

    created = client.post("/api/v1/users", headers=owner_headers, json={
        "full_name": "Revocable Technician",
        "email": "revocable-tech@example.com",
        "password": "technician-password-42",
        "role": "staff",
    })
    assert created.status_code == 201, created.text
    technician = client.post("/api/v1/auth/login", json={
        "email": "revocable-tech@example.com",
        "password": "technician-password-42",
    })
    assert technician.status_code == 200, technician.text
    tokens = technician.json()
    tech_headers = {"Authorization": f"Bearer {tokens['access_token']}"}
    assert client.get("/api/v1/auth/me", headers=tech_headers).status_code == 200

    deactivated = client.patch(
        f"/api/v1/users/{created.json()['id']}",
        headers=owner_headers,
        json={"is_active": False},
    )
    assert deactivated.status_code == 200, deactivated.text
    assert deactivated.json()["is_active"] is False
    assert client.get("/api/v1/auth/me", headers=tech_headers).status_code == 401
    assert client.post(
        "/api/v1/auth/refresh",
        json={"refresh_token": tokens["refresh_token"]},
    ).status_code == 401



def test_technician_creation_requires_invitation(client):
    owner = register(client, "invitation-only-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    response = client.post("/api/v1/users", headers=headers, json={
        "full_name": "No Direct Technician",
        "email": "no-direct-technician@example.com",
        "password": "technician-password-42",
        "role": "technician",
    })
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "technician_invitation_required"
