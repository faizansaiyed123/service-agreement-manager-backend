def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_document_is_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/customers" in response.json()["paths"]



def test_cors_allows_idempotency_key_and_exposes_backend_headers(client):
    response = client.options(
        "/api/v1/invoices",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert response.status_code == 200
    assert "Idempotency-Key" in response.headers["access-control-allow-headers"]
    assert "X-Request-ID" in response.headers["access-control-expose-headers"]
    assert "X-Attachment-SHA256" in response.headers["access-control-expose-headers"]
