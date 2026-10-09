def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_document_is_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/customers" in response.json()["paths"]
