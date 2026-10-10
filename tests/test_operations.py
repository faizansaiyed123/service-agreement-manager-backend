from datetime import date


def make_site(client, headers):
    response = client.post("/api/v1/customers", headers=headers, json={"name": "Maintenance Customer"})
    assert response.status_code == 201, response.text
    customer = response.json()
    response = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Primary Site", "address_line1": "14 Service Lane", "city": "Austin",
    })
    assert response.status_code == 201, response.text
    return customer, response.json()


def test_schedule_generation_is_idempotent_and_tenant_scoped(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Schedule HVAC", "full_name": "Schedule Owner",
        "email": "schedule-owner@example.com", "password": "correct-horse-battery-42",
    }).json()
    stranger = client.post("/api/v1/auth/register", json={
        "company_name": "Different HVAC", "full_name": "Different Owner",
        "email": "different-owner@example.com", "password": "correct-horse-battery-43",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    customer, location = make_site(client, headers)
    created = client.post("/api/v1/maintenance/schedules", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "name": "Monthly system inspection", "frequency": "monthly",
        "next_due_date": date.today().isoformat(), "checklist_template": ["Inspect filter", "Test thermostat"],
    })
    assert created.status_code == 201, created.text
    schedule_id = created.json()["id"]
    assert client.get(f"/api/v1/maintenance/schedules/{schedule_id}", headers=other_headers).status_code == 404
    request = {"occurrence_date": date.today().isoformat()}
    first = client.post(f"/api/v1/maintenance/schedules/{schedule_id}/generate", headers=headers, json=request)
    assert first.status_code == 201, first.text
    retry = client.post(f"/api/v1/maintenance/schedules/{schedule_id}/generate", headers=headers, json=request)
    assert retry.status_code == 200, retry.text
    assert retry.json()["id"] == first.json()["id"]
    listed = client.get("/api/v1/work-orders", headers=headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1
    assert listed.json()[0]["work_order_number"] == "WO-000001"


def test_technician_assignment_start_and_checklist_completion(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Dispatch HVAC", "full_name": "Dispatch Owner",
        "email": "dispatch-owner@example.com", "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    customer, location = make_site(client, headers)
    technician = client.post("/api/v1/users", headers=headers, json={
        "full_name": "Assigned Technician", "email": "assigned-tech@example.com",
        "password": "technician-password-42", "role": "technician",
    })
    assert technician.status_code == 201, technician.text
    today = date.today()
    schedule = client.post("/api/v1/maintenance/schedules", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "name": "Maintenance visit", "frequency": "annual", "next_due_date": today.isoformat(),
        "checklist_template": ["Inspect filter", "Test thermostat"],
    })
    assert schedule.status_code == 201, schedule.text
    order = client.post(f"/api/v1/maintenance/schedules/{schedule.json()['id']}/generate", headers=headers, json={"occurrence_date": today.isoformat()})
    assert order.status_code == 201, order.text
    order_id = order.json()["id"]
    assigned = client.post(f"/api/v1/work-orders/{order_id}/assign", headers=headers, json={"technician_user_id": technician.json()["id"]})
    assert assigned.status_code == 200
    assert assigned.json()["status"] == "assigned"

    login = client.post("/api/v1/auth/login", json={
        "email": "assigned-tech@example.com", "password": "technician-password-42",
    })
    assert login.status_code == 200, login.text
    tech_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    started = client.post(f"/api/v1/work-orders/{order_id}/start", headers=tech_headers)
    assert started.status_code == 200, started.text
    incomplete = client.post(f"/api/v1/work-orders/{order_id}/complete", headers=tech_headers, json={
        "checklist_results": {"Inspect filter": True},
    })
    assert incomplete.status_code == 422
    completed = client.post(f"/api/v1/work-orders/{order_id}/complete", headers=tech_headers, json={
        "completion_notes": "Service completed", "technician_findings": "No faults found",
        "checklist_results": {"Inspect filter": True, "Test thermostat": True},
        "customer_signoff_name": "Site Manager",
    })
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert client.post(f"/api/v1/work-orders/{order_id}/cancel", headers=headers, json={"reason": "Too late"}).status_code == 409
