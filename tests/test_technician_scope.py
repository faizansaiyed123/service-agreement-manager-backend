import re
from datetime import date

from sqlalchemy import select

from conftest import TestingSession
from app.models import NotificationOutbox


def register_owner(client, email="technician-scope-owner@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Technician Scope HVAC",
        "full_name": "Dispatch Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def make_branch(client, headers, name="Austin Branch", code="AUS", is_primary=True):
    response = client.post("/api/v1/branches", headers=headers, json={
        "name": name,
        "code": code,
        "timezone": "America/Chicago",
        "country_code": "US",
        "city": "Austin",
        "is_primary": is_primary,
    })
    assert response.status_code == 201, response.text
    return response.json()


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


def invite_technician(client, owner_headers, branch_id, full_name, email, password, skills):
    invited = client.post("/api/v1/team/invitations", headers=owner_headers, json={
        "full_name": full_name,
        "email": email,
        "branch_ids": [branch_id],
        "skills": skills,
    })
    assert invited.status_code == 201, invited.text
    with TestingSession() as db:
        notification = db.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.recipient_email == email,
                NotificationOutbox.event_type == "team.technician_invited",
            )
            .order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc())
            .limit(1)
        )
        assert notification is not None
        match = re.search(r"/team/invitation/([^\s/]+)", notification.body)
        assert match is not None, notification.body
        token = match.group(1).rstrip(".,)")
    accepted = client.post(
        f"/api/v1/team/invitations/public/{token}/accept",
        json={"password": password},
    )
    assert accepted.status_code == 201, accepted.text
    headers = {"Authorization": "Bearer " + accepted.json()["access_token"]}
    current = client.get("/api/v1/auth/me", headers=headers)
    assert current.status_code == 200, current.text
    return current.json(), headers


def test_technician_can_only_list_and_open_assigned_work_orders(client):
    owner_headers = register_owner(client)
    branch = make_branch(client, owner_headers)
    second_branch = make_branch(client, owner_headers, name="Dallas Branch", code="DAL", is_primary=False)
    customer_a, location_a = make_site(client, owner_headers, "Customer A")
    customer_b, location_b = make_site(client, owner_headers, "Customer B")

    technician_a, tech_headers = invite_technician(
        client, owner_headers, branch["id"], "Technician A",
        "technician-a@example.com", "technician-password-42", ["AC Maintenance"],
    )
    technician_b, _ = invite_technician(
        client, owner_headers, branch["id"], "Technician B",
        "technician-b@example.com", "another-technician-password-42", ["Refrigeration"],
    )

    order_a = client.post("/api/v1/work-orders", headers=owner_headers, json={
        "customer_id": customer_a["id"],
        "service_location_id": location_a["id"],
        "branch_id": branch["id"],
        "title": "Technician A visit",
        "required_skill": "AC Maintenance",
        "scheduled_for": date.today().isoformat(),
    })
    order_b = client.post("/api/v1/work-orders", headers=owner_headers, json={
        "customer_id": customer_b["id"],
        "service_location_id": location_b["id"],
        "branch_id": branch["id"],
        "title": "Technician B visit",
        "required_skill": "Refrigeration",
        "scheduled_for": date.today().isoformat(),
    })
    assert order_a.status_code == order_b.status_code == 201, f"{order_a.text} {order_b.text}"

    mismatch = client.post(
        f"/api/v1/work-orders/{order_b.json()['id']}/assign",
        headers=owner_headers,
        json={"technician_user_id": technician_a["id"]},
    )
    assert mismatch.status_code == 409, mismatch.text
    assert "technician_skill_mismatch" in mismatch.text

    assert client.post(
        f"/api/v1/work-orders/{order_a.json()['id']}/assign",
        headers=owner_headers,
        json={"technician_user_id": technician_a["id"]},
    ).status_code == 200
    assert client.post(
        f"/api/v1/work-orders/{order_b.json()['id']}/assign",
        headers=owner_headers,
        json={"technician_user_id": technician_b["id"]},
    ).status_code == 200

    skill_change = client.patch(
        f"/api/v1/work-orders/{order_a.json()['id']}",
        headers=owner_headers,
        json={"required_skill": "Refrigeration"},
    )
    assert skill_change.status_code == 409, skill_change.text
    assert "technician_skill_mismatch" in skill_change.text

    branch_change = client.patch(
        f"/api/v1/team/technicians/{technician_a['id']}",
        headers=owner_headers,
        json={"branch_ids": [second_branch["id"]], "skills": ["AC Maintenance"]},
    )
    assert branch_change.status_code == 409, branch_change.text
    assert "technician_has_active_work_at_branch" in branch_change.text

    skills_change = client.patch(
        f"/api/v1/team/technicians/{technician_a['id']}",
        headers=owner_headers,
        json={"branch_ids": [branch["id"]], "skills": ["Refrigeration"]},
    )
    assert skills_change.status_code == 409, skills_change.text
    assert "technician_has_active_work_for_skill" in skills_change.text

    listed = client.get("/api/v1/work-orders?limit=100", headers=tech_headers)
    assert listed.status_code == 200, listed.text
    assert [item["id"] for item in listed.json()] == [order_a.json()["id"]]
    assigned = listed.json()[0]
    assert assigned["customer_name"] == "Customer A"
    assert assigned["service_location_name"] == "Primary Site"
    assert "14 Service Lane" in assigned["service_location_address"]
    assert client.get(f"/api/v1/work-orders/{order_a.json()['id']}", headers=tech_headers).status_code == 200
    assert client.get(f"/api/v1/work-orders/{order_b.json()['id']}", headers=tech_headers).status_code == 404
    assert client.get(f"/api/v1/work-orders/{order_b.json()['id']}/events", headers=tech_headers).status_code == 404


def test_technician_can_only_read_checklists_for_schedules_on_assigned_orders(client):
    owner_headers = register_owner(client, "schedule-scope-owner@example.com")
    branch = make_branch(client, owner_headers)
    customer, location = make_site(client, owner_headers, "Checklist Customer")
    technician, tech_headers = invite_technician(
        client, owner_headers, branch["id"], "Schedule Technician",
        "schedule-technician@example.com", "technician-password-43", ["HVAC"],
    )
    schedule = client.post("/api/v1/maintenance/schedules", headers=owner_headers, json={
        "branch_id": branch["id"],
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "name": "Assigned checklist",
        "required_skill": "HVAC",
        "frequency": "monthly",
        "next_due_date": date.today().isoformat(),
        "checklist_template": ["Inspect equipment"],
    })
    assert schedule.status_code == 201, schedule.text
    order = client.post(
        f"/api/v1/maintenance/schedules/{schedule.json()['id']}/generate",
        headers=owner_headers,
        json={"occurrence_date": date.today().isoformat()},
    )
    assert order.status_code == 201, order.text
    assert order.json()["required_skill"] == "HVAC"
    assert client.post(
        f"/api/v1/work-orders/{order.json()['id']}/assign",
        headers=owner_headers,
        json={"technician_user_id": technician["id"]},
    ).status_code == 200
    own = client.get(
        f"/api/v1/maintenance/schedules/{schedule.json()['id']}",
        headers=tech_headers,
    )
    assert own.status_code == 200, own.text
    assert own.json()["checklist_template"] == ["Inspect equipment"]
