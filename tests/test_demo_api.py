from fastapi.testclient import TestClient

from app.demo.main import app

client = TestClient(app)


def test_demo_health_and_seeded_api():
    assert client.get("/health/live").json() == {"status": "ok"}
    response = client.get("/api/v1/customers")
    assert response.status_code == 200
    assert len(response.json()) >= 4


def test_demo_auth_is_deterministic():
    response = client.post("/api/v1/auth/login", json={"email": "anything@example.com", "password": "anything"})
    assert response.status_code == 200
    assert response.json()["authenticated"] is True


def test_demo_mutation_is_in_memory():
    response = client.post("/api/v1/customers", json={"name": "Demo Customer", "kind": "commercial"})
    assert response.status_code == 200
    created = response.json()
    assert created["name"] == "Demo Customer"
    listed = client.get("/api/v1/customers").json()
    assert any(item["id"] == created["id"] for item in listed)
