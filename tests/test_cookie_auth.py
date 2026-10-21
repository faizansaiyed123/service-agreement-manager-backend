def test_browser_auth_uses_httponly_cookies_without_exposing_tokens(client):
    origin = "http://localhost:3000"
    email = "cookie-session@example.com"
    registered = client.post(
        "/api/v1/auth/register",
        headers={"Origin": origin},
        json={
            "company_name": "Cookie HVAC",
            "full_name": "Cookie Owner",
            "email": email,
            "password": "correct-horse-battery-42",
        },
    )
    assert registered.status_code == 201, registered.text
    assert registered.json()["authenticated"] is True
    assert "access_token" not in registered.json()
    assert "refresh_token" not in registered.json()
    set_cookies = registered.headers.get_list("set-cookie")
    access_cookie = next(value for value in set_cookies if value.startswith("sam_access="))
    refresh_cookie = next(value for value in set_cookies if value.startswith("sam_refresh="))
    assert "HttpOnly" in access_cookie
    assert "Path=/api/v1;" in access_cookie
    assert "HttpOnly" in refresh_cookie
    assert "Path=/api/v1/auth/refresh" in refresh_cookie

    assert client.get("/api/v1/auth/me").status_code == 200

    refreshed = client.post("/api/v1/auth/refresh", headers={"Origin": origin})
    assert refreshed.status_code == 200, refreshed.text
    assert refreshed.json()["authenticated"] is True
    assert "access_token" not in refreshed.json()
    assert "refresh_token" not in refreshed.json()

    assert client.post("/api/v1/auth/logout").status_code == 403
    assert client.post(
        "/api/v1/auth/logout",
        headers={"Origin": "https://attacker.example"},
    ).status_code == 403
    logged_out = client.post("/api/v1/auth/logout", headers={"Origin": origin})
    assert logged_out.status_code == 204
    assert any("sam_access=" in value and "Max-Age=0" in value for value in logged_out.headers.get_list("set-cookie"))


def test_browser_requests_cannot_use_bearer_tokens(client):
    registered = client.post("/api/v1/auth/register", json={
        "company_name": "Bearer HVAC",
        "full_name": "Bearer Owner",
        "email": "browser-bearer@example.com",
        "password": "correct-horse-battery-42",
    })
    assert registered.status_code == 201, registered.text
    access_token = registered.json()["access_token"]
    response = client.get(
        "/api/v1/auth/me",
        headers={
            "Origin": "http://localhost:3000",
            "Authorization": f"Bearer {access_token}",
        },
    )
    assert response.status_code == 401


def test_login_throttles_repeated_bad_password_attempts(client):
    email = "throttle-login@example.com"
    registered = client.post("/api/v1/auth/register", json={
        "company_name": "Throttle HVAC",
        "full_name": "Throttle Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert registered.status_code == 201
    for _ in range(10):
        response = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
        assert response.status_code == 401
    limited = client.post("/api/v1/auth/login", json={"email": email, "password": "wrong-password"})
    assert limited.status_code == 429
