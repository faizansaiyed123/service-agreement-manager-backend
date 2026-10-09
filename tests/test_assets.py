def test_equipment_and_service_catalog_are_company_scoped(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Asset HVAC", "full_name": "Owner", "email": "assets@example.com",
        "password": "correct-horse-battery-42",
    }).json()
    other = client.post("/api/v1/auth/register", json={
        "company_name": "Other HVAC", "full_name": "Other Owner", "email": "other-assets@example.com",
        "password": "correct-horse-battery-43",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {other['access_token']}"}
    customer = client.post("/api/v1/customers", headers=headers, json={"name": "Homeowner"})
    assert customer.status_code == 201, customer.text
    customer_id = customer.json()["id"]
    location = client.post(f"/api/v1/customers/{customer_id}/service-locations", headers=headers, json={
        "name": "Residence", "address_line1": "20 Oak Road", "city": "Austin",
    })
    assert location.status_code == 201, location.text

    equipment = client.post("/api/v1/equipment", headers=headers, json={
        "customer_id": customer_id, "service_location_id": location.json()["id"],
        "category": "heat-pump", "manufacturer": "Example HVAC", "serial_number": "SN-987",
    })
    assert equipment.status_code == 201, equipment.text
    equipment_id = equipment.json()["id"]
    assert client.get(f"/api/v1/equipment/{equipment_id}", headers=headers).status_code == 200
    assert client.get(f"/api/v1/equipment/{equipment_id}", headers=other_headers).status_code == 404

    catalog = client.post("/api/v1/service-catalog", headers=headers, json={
        "service_code": "HP-TUNEUP", "name": "Heat pump tune-up", "category": "maintenance",
        "unit_price": "125.50", "duration_minutes": 90,
    })
    assert catalog.status_code == 201, catalog.text
    assert catalog.json()["unit_price"] == "125.50"
    assert client.get("/api/v1/service-catalog", headers=other_headers).json() == []
    duplicate = client.post("/api/v1/service-catalog", headers=headers, json={
        "service_code": "hp-tuneup", "name": "Duplicate code", "category": "maintenance",
    })
    assert duplicate.status_code == 409
