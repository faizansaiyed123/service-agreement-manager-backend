from datetime import UTC, datetime, timedelta


def make_agreement(client, headers, email):
    today = datetime.now(UTC).date()
    customer_res = client.post("/api/v1/customers", headers=headers, json={"name": "Renewal Customer", "email": email})
    assert customer_res.status_code == 201, customer_res.text
    customer = customer_res.json()
    location_res = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Site", "address_line1": "22 Renewal Way", "city": "Austin",
    })
    assert location_res.status_code == 201, location_res.text
    agreement_res = client.post("/api/v1/agreements", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location_res.json()["id"],
        "title": "Annual service agreement", "start_date": today.isoformat(),
        "end_date": (today + timedelta(days=30)).isoformat(),
        "lines": [{"service_code": "ANNUAL", "name": "Annual care", "quantity": "1", "unit_price": "100.00"}],
    })
    assert agreement_res.status_code == 201, agreement_res.text
    agreement = agreement_res.json()
    proposed = client.post(f"/api/v1/agreements/{agreement['id']}/propose", headers=headers)
    assert proposed.status_code == 200, proposed.text
    accepted = client.post(f"/api/v1/agreements/{agreement['id']}/accept", headers=headers, json={
        "accepted_by_name": "Current Customer", "method": "manual",
    })
    assert accepted.status_code == 200, accepted.text
    return agreement, location_res.json()


def test_renewal_offer_acceptance_creates_snapshot_successor(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Renewal HVAC", "full_name": "Renewal Owner",
        "email": "renewal-owner@example.com", "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    source, _ = make_agreement(client, headers, "renewal-client@example.com")
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(source["end_date"]).date() + timedelta(days=1)
    body = {
        "proposed_start_date": start.isoformat(),
        "proposed_end_date": (start + timedelta(days=365)).isoformat(),
        "expires_on": (today + timedelta(days=14)).isoformat(),
        "title": "Renewed annual service",
        "lines": [{
            "service_code": "ANNUAL", "name": "Annual care - renewal", "description": "Updated annual visit",
            "quantity": "1", "unit_price": "125.00",
        }],
    }
    created = client.post(f"/api/v1/agreements/{source['id']}/renewals", headers=headers, json=body)
    assert created.status_code == 201, created.text
    offer = created.json()
    assert offer["snapshot"]["total_amount"] == "125.00"
    assert offer["status"] == "offered"

    duplicate = client.post(f"/api/v1/agreements/{source['id']}/renewals", headers=headers, json=body)
    assert duplicate.status_code == 409

    accepted = client.post(f"/api/v1/agreements/{source['id']}/renewals/{offer['id']}/accept", headers=headers, json={
        "accepted_by_name": "Renewal Customer", "method": "electronic", "reference": "renewal-signature-1",
    })
    assert accepted.status_code == 200, accepted.text
    successor = accepted.json()
    assert successor["id"] != source["id"]
    assert successor["status"] == "accepted"
    assert successor["start_date"] == start.isoformat()
    assert successor["total_amount"] == "125.00"
    assert successor["lines"][0]["unit_price"] == "125.00"
    assert successor["accepted_by_name"] == "Renewal Customer"
    offer_again = client.post(f"/api/v1/agreements/{source['id']}/renewals/{offer['id']}/accept", headers=headers, json={
        "accepted_by_name": "Renewal Customer", "method": "electronic",
    })
    assert offer_again.status_code == 409
    listed = client.get(f"/api/v1/agreements/{source['id']}/renewals", headers=headers)
    assert listed.status_code == 200
    assert listed.json()[0]["renewed_agreement_id"] == successor["id"]
    events = client.get(f"/api/v1/agreements/{source['id']}/events", headers=headers).json()
    assert "agreement.renewal_offered" in [item["event_type"] for item in events]
    assert "agreement.renewal_accepted" in [item["event_type"] for item in events]


def test_renewal_decline_and_tenant_isolation(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Renewal Tenant One", "full_name": "Tenant Owner",
        "email": "renewal-one@example.com", "password": "correct-horse-battery-42",
    }).json()
    other = client.post("/api/v1/auth/register", json={
        "company_name": "Renewal Tenant Two", "full_name": "Other Owner",
        "email": "renewal-two@example.com", "password": "correct-horse-battery-43",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    source, _ = make_agreement(client, headers, "renewal-one-client@example.com")
    today = datetime.now(UTC).date()
    start = datetime.fromisoformat(source["end_date"]).date() + timedelta(days=1)
    body = {
        "proposed_start_date": start.isoformat(),
        "proposed_end_date": (start + timedelta(days=365)).isoformat(),
        "expires_on": (today + timedelta(days=14)).isoformat(),
    }
    offer = client.post(f"/api/v1/agreements/{source['id']}/renewals", headers=headers, json=body)
    assert offer.status_code == 201, offer.text
    offer_id = offer.json()["id"]
    assert client.get(f"/api/v1/agreements/{source['id']}/renewals", headers=other_headers).status_code == 404
    declined = client.post(f"/api/v1/agreements/{source['id']}/renewals/{offer_id}/decline", headers=headers, json={
        "reason": "Customer selected a different provider",
    })
    assert declined.status_code == 200, declined.text
    assert declined.json()["status"] == "declined"
    assert declined.json()["decline_reason"] == "Customer selected a different provider"
