from datetime import date, timedelta


def setup_location(client, headers):
    customer_response = client.post("/api/v1/customers", headers=headers, json={"name": "Agreement Customer"})
    assert customer_response.status_code == 201, customer_response.text
    customer = customer_response.json()
    response = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Main Site", "address_line1": "10 Service Road", "city": "Austin",
    })
    assert response.status_code == 201, response.text
    return customer, response.json()


def test_agreement_lifecycle_versions_events_and_tenant_isolation(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Agreement HVAC", "full_name": "Agreement Owner",
        "email": "agreements@example.com", "password": "correct-horse-battery-42",
    }).json()
    stranger = client.post("/api/v1/auth/register", json={
        "company_name": "Other HVAC", "full_name": "Other Owner",
        "email": "other-agreement@example.com", "password": "correct-horse-battery-43",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    stranger_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    customer, location = setup_location(client, headers)
    start = date.today()
    created = client.post("/api/v1/agreements", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "title": "Annual HVAC care", "start_date": start.isoformat(),
        "end_date": (start + timedelta(days=365)).isoformat(), "billing_frequency": "annual",
        "terms_text": "Two planned visits",
        "lines": [{"name": "Annual maintenance", "service_code": "CUSTOM-MAINT", "quantity": "2", "unit_price": "125.50"}],
    })
    assert created.status_code == 201, created.text
    agreement = created.json()
    assert agreement["agreement_number"] == "SA-000001"
    assert agreement["total_amount"] == "251.00"
    agreement_id = agreement["id"]
    assert client.get(f"/api/v1/agreements/{agreement_id}", headers=stranger_headers).status_code == 404
    assert client.patch(f"/api/v1/agreements/{agreement_id}", headers=headers, json={"title": "Updated care"}).status_code == 200

    proposed = client.post(f"/api/v1/agreements/{agreement_id}/propose", headers=headers)
    assert proposed.status_code == 200, proposed.text
    assert proposed.json()["status"] == "proposed"
    versions = client.get(f"/api/v1/agreements/{agreement_id}/versions", headers=headers)
    assert versions.status_code == 200
    assert versions.json()[0]["snapshot"]["total_amount"] == "251.00"
    accepted = client.post(f"/api/v1/agreements/{agreement_id}/accept", headers=headers, json={
        "accepted_by_name": "Jamie Customer", "method": "electronic", "reference": "signature-ref-42",
    })
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["status"] == "active"
    assert accepted.json()["accepted_by_name"] == "Jamie Customer"
    assert client.patch(f"/api/v1/agreements/{agreement_id}", headers=headers, json={"title": "Forbidden edit"}).status_code == 409
    events = client.get(f"/api/v1/agreements/{agreement_id}/events", headers=headers)
    assert events.status_code == 200
    assert [event["event_type"] for event in events.json()] == [
        "agreement.created", "agreement.draft_updated", "agreement.proposed", "agreement.accepted"
    ]


def test_catalog_prices_are_snapshotted_and_transitions_are_guarded(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Snapshot HVAC", "full_name": "Snapshot Owner",
        "email": "snapshot@example.com", "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    customer, location = setup_location(client, headers)
    catalog = client.post("/api/v1/service-catalog", headers=headers, json={
        "service_code": "TUNEUP", "name": "Spring tune-up", "category": "maintenance",
        "unit_price": "89.50", "duration_minutes": 60,
    })
    assert catalog.status_code == 201, catalog.text
    today = date.today()
    created = client.post("/api/v1/agreements", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "title": "Preventive plan", "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=365)).isoformat(),
        "lines": [{"catalog_item_id": catalog.json()["id"], "quantity": "2"}],
    })
    assert created.status_code == 201, created.text
    assert created.json()["total_amount"] == "179.00"
    client.patch(f"/api/v1/service-catalog/{catalog.json()['id']}", headers=headers, json={"unit_price": "120.00"})
    again = client.get(f"/api/v1/agreements/{created.json()['id']}", headers=headers)
    assert again.json()["lines"][0]["unit_price"] == "89.50"
    assert again.json()["total_amount"] == "179.00"
    assert client.post(f"/api/v1/agreements/{created.json()['id']}/accept", headers=headers, json={
        "accepted_by_name": "Customer", "method": "manual",
    }).status_code == 409
