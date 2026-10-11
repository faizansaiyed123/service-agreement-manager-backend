def register(client, company, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company,
        "full_name": "Import Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_customer_import_preview_and_partial_result(client):
    headers = register(client, "Import HVAC", "import@example.com")
    preview = client.post("/api/v1/customers/imports/preview", headers=headers, json={"rows": [
        {"name": "Valid One", "kind": "commercial", "email": "valid@example.com"},
        {"name": "", "kind": "commercial"},
        {"name": "Valid One", "kind": "commercial", "email": "valid@example.com"},
    ]})
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["total_rows"] == 3
    assert body["valid_rows"] == 1
    assert body["invalid_rows"] == 2
    assert body["rows"][1]["error_code"] == "row_validation_failed"
    assert body["rows"][2]["error_code"] == "duplicate_import_row"

    imported = client.post("/api/v1/customers/imports", headers=headers, json={"rows": [
        {"name": "Valid One", "kind": "commercial", "email": "valid@example.com"},
        {"name": "", "kind": "commercial"},
    ]})
    assert imported.status_code == 201, imported.text
    job = imported.json()
    assert job["status"] == "partial"
    assert job["total_rows"] == 2
    assert job["imported_rows"] == 1
    assert job["failed_rows"] == 1

    detail = client.get(f"/api/v1/customers/imports/{job['id']}", headers=headers)
    assert detail.status_code == 200
    rows = detail.json()["rows"]
    failed = next(row for row in rows if row["status"] == "failed")
    assert failed["error_code"] == "row_validation_failed"
    assert client.get("/api/v1/customers?limit=10", headers=headers).json()[0]["name"] == "Valid One"

    corrected = client.put(
        f"/api/v1/customers/imports/{job['id']}/rows/{failed['id']}",
        headers=headers,
        json={"name": "Corrected Customer", "email": "corrected@example.com"},
    )
    assert corrected.status_code == 200, corrected.text
    assert corrected.json()["status"] == "pending"

    retried = client.post(f"/api/v1/customers/imports/{job['id']}/retry", headers=headers)
    assert retried.status_code == 200, retried.text
    assert retried.json()["status"] == "completed"
    assert retried.json()["imported_rows"] == 2
    assert retried.json()["failed_rows"] == 0

    names = {row["name"] for row in client.get("/api/v1/customers?limit=10", headers=headers).json()}
    assert names == {"Valid One", "Corrected Customer"}


def test_customer_import_rejects_existing_email_without_corrupting_job(client):
    headers = register(client, "Existing Import HVAC", "existing-import@example.com")
    created = client.post("/api/v1/customers", headers=headers, json={
        "name": "Existing Customer",
        "email": "existing@example.com",
    })
    assert created.status_code == 201, created.text

    imported = client.post("/api/v1/customers/imports", headers=headers, json={"rows": [
        {"name": "Another Name", "email": "existing@example.com"},
        {"name": "New Customer", "email": "new@example.com"},
    ]})
    assert imported.status_code == 201, imported.text
    job = imported.json()
    assert job["status"] == "partial"
    assert job["imported_rows"] == 1
    assert job["failed_rows"] == 1

    detail = client.get(f"/api/v1/customers/imports/{job['id']}", headers=headers).json()
    errors = [row["error_code"] for row in detail["rows"] if row["status"] == "failed"]
    assert errors == ["customer_email_exists"]


def test_customer_import_is_idempotent_with_same_key(client):
    headers = register(client, "Idempotent Import HVAC", "idempotent-import@example.com")
    headers["Idempotency-Key"] = "customer-import-001"
    rows = {"rows": [
        {"name": "Idempotent Customer", "kind": "commercial", "email": "idem@example.com"},
    ]}

    first = client.post("/api/v1/customers/imports", headers=headers, json=rows)
    assert first.status_code == 201, first.text
    first_job = first.json()

    replay = client.post("/api/v1/customers/imports", headers=headers, json=rows)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first_job["id"]

    changed = client.post("/api/v1/customers/imports", headers=headers, json={"rows": [
        {"name": "Different Customer", "email": "different@example.com"},
    ]})
    assert changed.status_code == 409, changed.text
    assert changed.json()["error"]["code"] == "idempotency_key_reused"

    customers = client.get("/api/v1/customers?limit=10", headers=headers)
    assert customers.status_code == 200
    assert [row["name"] for row in customers.json()] == ["Idempotent Customer"]
