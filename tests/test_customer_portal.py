import re
import uuid

from sqlalchemy import select

from conftest import TestingSession
from app.models import NotificationOutbox


def register_owner(client):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Customer Portal HVAC",
        "full_name": "Business Owner",
        "email": "portal-owner@example.com",
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": "Bearer " + response.json()["access_token"]}


def create_customer(client, owner_headers, name, email):
    response = client.post("/api/v1/customers", headers=owner_headers, json={
        "name": name,
        "kind": "commercial",
        "email": email,
        "phone": "+1 555 0100",
    })
    assert response.status_code == 201, response.text
    customer = response.json()
    location = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=owner_headers,
        json={
            "name": "Main site",
            "address_line1": "10 Service Way",
            "city": "Austin",
            "country_code": "US",
        },
    )
    assert location.status_code == 201, location.text
    return customer, location.json()


def invite_customer(client, owner_headers, customer_id, email):
    response = client.post(
        f"/api/v1/customer-portal/customers/{customer_id}/invite",
        headers=owner_headers,
        json={"full_name": "Customer Contact"},
    )
    assert response.status_code == 201, response.text
    with TestingSession() as db:
        notification = db.scalar(
            select(NotificationOutbox)
            .where(
                NotificationOutbox.recipient_email == email,
                NotificationOutbox.event_type == "customer.portal_invited",
            )
            .order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc())
            .limit(1)
        )
        assert notification is not None
        match = re.search(r"/customer-portal/invitation/([^\s/]+)", notification.body)
        assert match is not None, notification.body
        token = match.group(1).rstrip(".,)")
    accepted = client.post(
        f"/api/v1/customer-portal/invitations/public/{token}/accept",
        json={"full_name": "Customer Contact", "password": "customer-password-42"},
    )
    assert accepted.status_code == 201, accepted.text
    headers = {"Authorization": "Bearer " + accepted.json()["access_token"]}
    current = client.get("/api/v1/customer-portal/auth/me", headers=headers)
    assert current.status_code == 200, current.text
    return headers, current.json()


def test_customer_record_does_not_create_login_until_invited(client):
    owner_headers = register_owner(client)
    customer, _ = create_customer(client, owner_headers, "Northwind HVAC", "customer-portal@example.com")

    status = client.get(
        f"/api/v1/customer-portal/customers/{customer['id']}/access",
        headers=owner_headers,
    )
    assert status.status_code == 200, status.text
    assert status.json()["has_access"] is False
    assert status.json()["invitation_status"] is None

    portal_login = client.post("/api/v1/customer-portal/auth/login", json={
        "email": "customer-portal@example.com",
        "password": "customer-password-42",
    })
    assert portal_login.status_code == 401


def test_customer_portal_is_customer_scoped_and_can_be_revoked(client):
    owner_headers = register_owner(client)
    customer_a, location_a = create_customer(
        client, owner_headers, "Customer A", "customer-a-portal@example.com",
    )
    customer_b, location_b = create_customer(
        client, owner_headers, "Customer B", "customer-b-portal@example.com",
    )

    headers, identity = invite_customer(
        client, owner_headers, customer_a["id"], "customer-a-portal@example.com",
    )
    assert len(identity["memberships"]) == 1
    membership_id = identity["memberships"][0]["membership_id"]

    locations = client.get(
        f"/api/v1/customer-portal/memberships/{membership_id}/locations",
        headers=headers,
    )
    assert locations.status_code == 200, locations.text
    assert [item["id"] for item in locations.json()] == [location_a["id"]]
    assert location_b["id"] not in [item["id"] for item in locations.json()]

    assert client.get(
        f"/api/v1/customer-portal/memberships/{uuid.uuid4()}/locations",
        headers=headers,
    ).status_code == 404
    assert client.get(
        f"/api/v1/customer-portal/memberships/{membership_id}/payments",
        headers=headers,
    ).json() == []
    assert client.get(
        f"/api/v1/customer-portal/memberships/{membership_id}/documents",
        headers=headers,
    ).json() == []

    disabled = client.delete(
        f"/api/v1/customer-portal/customers/{customer_a['id']}/access",
        headers=owner_headers,
    )
    assert disabled.status_code == 204
    assert client.get("/api/v1/customer-portal/auth/me", headers=headers).status_code == 401
