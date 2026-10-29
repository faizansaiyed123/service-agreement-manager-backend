from datetime import date


def register_owner(client):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Technician Scope HVAC",
        "full_name": "Dispatch Owner",
        "email": "technician-scope-owner@example.com",
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def make_site(client, headers, name):
    customer_response = client.post("/api/v1/customers", headers=headers, json={"name": name})
    assert customer_response.status_code == 201, customer_response.text
    customer = customer_response.json()
    location_response = client.post(
        "/api/v1/customers/{}/service-locations".format(customer["id"]),
        headers=headers,
        json={"name": "Primary Site", "address_line1": "14 Service Lane", "city": "Austin"},
    )
    assert location_response.status_code == 201, location_response.text
    return customer, location_response.json()


def test_technician_can_only_list_and_open_assigned_work_orders(client):
    owner_headers = register_owner(client)
    customer_a, location_a = make_site(client, owner_headers, "Customer A")
    customer_b, location_b = make_site(client, owner_headers, "Customer B")

    technician_a = client.post("/api/v1/users", headers=owner_headers, json={
        "full_name": "Technician A",
        "email": "technician-a@example.com",
        "password": "technician-password-42",
        "role": "technician",
    })
    technician_b = client.post("/api/v1/users", headers=owner_headers, json={
        "full_name": "Technician B",
        "email": "technician-b@example.com",
        "password": "another-technician-password-42",
        "role": "technician",
    })
    assert technician_a.status_code == technician_b.status_code == 201

    order_a = client.post("/api/v1/work-orders", headers=owner_headers, json={
        "customer_id": customer_a["id"],
        "service_location_id": location_a["id"],
        "title": "Technician A visit",
        "scheduled_for": date.today().isoformat(),
    })
    order_b = client.post("/api/v1/work-orders", headers=owner_headers, json={
        "customer_id": customer_b["id"],
        "service_location_id": location_b["id"],
        "title": "Technician B visit",
        "scheduled_for": date.today().isoformat(),
    })
    assert order_a.status_code == order_b.status_code == 201
    assert client.post(
        "/api/v1/work-orders/{}/assign".format(order_a.json()["id"]),
        headers=owner_headers,
        json={"technician_user_id": technician_a.json()["id"]},
    ).status_code == 200
    assert client.post(
        "/api/v1/work-orders/{}/assign".format(order_b.json()["id"]),
        headers=owner_headers,
        json={"technician_user_id": technician_b.json()["id"]},
    ).status_code == 200

    login = client.post("/api/v1/auth/login", json={
        "email": "technician-a@example.com",
        "password": "technician-password-42",
    })
    assert login.status_code == 200, login.text
    tech_headers = {"Authorization": "Bearer " + login.json()["access_token"]}

    listed = client.get("/api/v1/work-orders?limit=100", headers=tech_headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [order_a.json()["id"]]
    assert client.get("/api/v1/work-orders/{}".format(order_a.json()["id"]), headers=tech_headers).status_code == 200
    assert client.get("/api/v1/work-orders/{}".format(order_b.json()["id"]), headers=tech_headers).status_code == 404
    assert client.get("/api/v1/work-orders/{}/events".format(order_b.json()["id"]), headers=tech_headers).status_code == 404


def test_technician_can_only_read_checklists_for_schedules_on_assigned_orders(client):
    owner_headers = register_owner(client)
    customer, location = make_site(client, owner_headers, "Checklist Customer")
    technician = client.post("/api/v1/users", headers=owner_headers, json={
        "full_name": "Schedule Technician",
        "email": "schedule-technician@example.com",
        "password": "technician-password-43",
        "role": "technician",
    })
    schedule = client.post("/api/v1/maintenance/schedules", headers=owner_headers, json={
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "name": "Assigned checklist",
        "frequency": "monthly",
        "next_due_date": date.today().isoformat(),
        "checklist_template": ["Inspect equipment"],
    })
    assert schedule.status_code == 201, schedule.text
    order = client.post(
        "/api/v1/maintenance/schedules/{}/generate".format(schedule.json()["id"]),
        headers=owner_headers,
        json={"occurrence_date": date.today().isoformat()},
    )
    assert order.status_code == 201, order.text
    assert client.post(
        "/api/v1/work-orders/{}/assign".format(order.json()["id"]),
        headers=owner_headers,
        json={"technician_user_id": technician.json()["id"]},
    ).status_code == 200

    login = client.post("/api/v1/auth/login", json={
        "email": "schedule-technician@example.com",
        "password": "technician-password-43",
    })
    assert login.status_code == 200, login.text
    tech_headers = {"Authorization": "Bearer " + login.json()["access_token"]}
    own = client.get(
        "/api/v1/maintenance/schedules/{}".format(schedule.json()["id"]),
        headers=tech_headers,
    )
    assert own.status_code == 200, own.text
    assert own.json()["checklist_template"] == ["Inspect equipment"]
