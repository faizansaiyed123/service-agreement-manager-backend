def register(client, company, name, email, password):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company, "full_name": name, "email": email, "password": password,
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_registration_duplicate_login_and_refresh_rotation(client):
    payload = {
        "company_name": "Reliable HVAC", "full_name": "Alex Example",
        "email": "alex@example.com", "password": "correct-horse-battery-42",
    }
    first = client.post("/api/v1/auth/register", json=payload)
    assert first.status_code == 201
    assert first.json()["token_type"] == "bearer"
    assert client.post("/api/v1/auth/register", json=payload).status_code == 409
    login = client.post("/api/v1/auth/login", json={"email": payload["email"], "password": payload["password"]})
    assert login.status_code == 200
    old_refresh = login.json()["refresh_token"]
    refreshed = client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh})
    assert refreshed.status_code == 200
    assert refreshed.json()["refresh_token"] != old_refresh
    assert client.post("/api/v1/auth/refresh", json={"refresh_token": old_refresh}).status_code == 401


def test_customer_contacts_locations_and_tenant_isolation(client):
    north = register(client, "North HVAC", "North Owner", "north@example.com", "correct-horse-battery-42")
    south = register(client, "South Plumbing", "South Owner", "south@example.com", "correct-horse-battery-43")
    north_headers = {"Authorization": f"Bearer {north['access_token']}"}
    south_headers = {"Authorization": f"Bearer {south['access_token']}"}
    created = client.post("/api/v1/customers", headers=north_headers, json={
        "name": "Acme Offices", "kind": "commercial", "email": "ops@acme.test",
    })
    assert created.status_code == 201
    customer_id = created.json()["id"]
    assert created.json()["customer_number"] == "C-000001"
    assert client.get(f"/api/v1/customers/{customer_id}", headers=north_headers).status_code == 200
    assert client.get(f"/api/v1/customers/{customer_id}", headers=south_headers).status_code == 404
    contact = client.post(f"/api/v1/customers/{customer_id}/contacts", headers=north_headers, json={"full_name": "Site Contact"})
    assert contact.status_code == 201, contact.text
    location = client.post(f"/api/v1/customers/{customer_id}/service-locations", headers=north_headers, json={
        "name": "Main Site", "address_line1": "1 Main St", "city": "Austin", "country_code": "us",
    })
    assert location.status_code == 201, location.text
    assert location.json()["country_code"] == "US"
    assert client.get(f"/api/v1/customers/{customer_id}/contacts", headers=south_headers).status_code == 404


def test_authentication_is_required_and_password_is_validated(client):
    assert client.get("/api/v1/customers").status_code == 401
    invalid = client.post("/api/v1/auth/register", json={
        "company_name": "HVAC", "full_name": "Owner", "email": "owner@example.com", "password": "short",
    })
    assert invalid.status_code == 422


def test_customer_search_pagination_and_deactivation(client):
    auth = register(client, "Search HVAC", "Owner", "search@example.com", "correct-horse-battery-42")
    headers = {"Authorization": f"Bearer {auth['access_token']}"}
    for customer_name in ("Alpha Office", "Beta Home"):
        result = client.post("/api/v1/customers", headers=headers, json={"name": customer_name})
        assert result.status_code == 201
    found = client.get("/api/v1/customers?q=Alpha&limit=1", headers=headers)
    assert found.status_code == 200
    assert len(found.json()) == 1 and found.json()[0]["name"] == "Alpha Office"
    customer_id = found.json()[0]["id"]
    assert client.delete(f"/api/v1/customers/{customer_id}", headers=headers).status_code == 204
    active = client.get("/api/v1/customers?status=active", headers=headers)
    assert all(item["id"] != customer_id for item in active.json())
