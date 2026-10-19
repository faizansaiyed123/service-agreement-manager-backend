def test_liveness(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_document_is_available(client):
    response = client.get("/openapi.json")
    assert response.status_code == 200
    assert "/api/v1/customers" in response.json()["paths"]



def test_cors_allows_idempotency_key_and_exposes_backend_headers(client):
    preflight = client.options(
        "/api/v1/invoices",
        headers={
            "Origin": "http://localhost:3000",
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "authorization,content-type,idempotency-key",
        },
    )
    assert preflight.status_code == 200
    assert "Idempotency-Key" in preflight.headers["access-control-allow-headers"]

    response = client.get(
        "/health/live",
        headers={"Origin": "http://localhost:3000"},
    )
    assert response.status_code == 200
    exposed = response.headers["access-control-expose-headers"]
    assert "X-Request-ID" in exposed
    assert "X-Attachment-SHA256" in exposed



def test_api_responses_set_private_cache_and_content_type_headers(client):
    response = client.get("/health/live")
    assert response.headers["cache-control"] == "no-store"
    assert response.headers["x-content-type-options"] == "nosniff"
    assert response.headers["referrer-policy"] == "strict-origin-when-cross-origin"
