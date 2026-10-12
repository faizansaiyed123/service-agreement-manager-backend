from datetime import date

from conftest import TestingSession
from app.core.config import get_settings
from app.models import SmsOutbox
from app.workers.sms import run_once as run_sms_once


def auth(client, company, email):
    body = client.post("/api/v1/auth/register", json={
        "company_name": company,
        "full_name": "Feature Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    }).json()
    return {"Authorization": f"Bearer {body['access_token']}"}


def test_branch_linked_work_order_and_maintenance_schedule(client):
    headers = auth(client, "Dispatch HVAC", "dispatch@example.com")
    primary = client.get("/api/v1/branches", headers=headers).json()
    assert primary

    branch = client.post("/api/v1/branches", headers=headers, json={
        "name": "South Branch",
        "code": "SOUTH",
        "timezone": "America/Chicago",
    })
    assert branch.status_code == 201, branch.text
    branch_id = branch.json()["id"]

    customer = client.post("/api/v1/customers", headers=headers, json={"name": "Dispatch Customer"}).json()
    location = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Dispatch Site", "address_line1": "1 Dispatch Way", "city": "Austin"},
    ).json()

    order = client.post("/api/v1/work-orders", headers=headers, json={
        "branch_id": branch_id,
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "title": "Branch service",
        "scheduled_for": date.today().isoformat(),
    })
    assert order.status_code == 201, order.text
    assert order.json()["branch_id"] == branch_id

    filtered = client.get(f"/api/v1/work-orders?branch_id={branch_id}", headers=headers)
    assert filtered.status_code == 200
    assert [row["id"] for row in filtered.json()] == [order.json()["id"]]

    schedule = client.post("/api/v1/maintenance/schedules", headers=headers, json={
        "branch_id": branch_id,
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "name": "Monthly Branch Maintenance",
        "frequency": "monthly",
        "next_due_date": date.today().isoformat(),
    })
    assert schedule.status_code == 201, schedule.text
    assert schedule.json()["branch_id"] == branch_id


def test_sms_provider_queue_and_fake_delivery(client):
    settings = get_settings()
    original = {
        "sms_provider": settings.sms_provider,
        "sms_api_url": settings.sms_api_url,
        "sms_from": settings.sms_from,
    }
    try:
        headers = auth(client, "SMS HVAC", "sms@example.com")
        assert client.post("/api/v1/sms", headers={**headers, "Idempotency-Key": "sms-disabled-1"}, json={
            "event_type": "customer.created",
            "recipient_phone": "+15550001111",
            "body": "hello",
        }).status_code == 503

        settings.sms_provider = "http"
        settings.sms_api_url = "https://sms.example.test/send"
        settings.sms_from = "+15550000000"

        response = client.post("/api/v1/sms", headers={**headers, "Idempotency-Key": "sms-test-1"}, json={
            "event_type": "customer.created",
            "recipient_phone": "+15550001111",
            "body": "hello",
        })
        assert response.status_code == 201, response.text
        replay = client.post("/api/v1/sms", headers={**headers, "Idempotency-Key": "sms-test-1"}, json={
            "event_type": "customer.created",
            "recipient_phone": "+15550001111",
            "body": "hello",
        })
        assert replay.status_code == 200
        assert replay.json()["id"] == response.json()["id"]

        def sender(sms):
            assert sms.recipient_phone == "+15550001111"
            return "sms-msg-1"

        assert run_sms_once(session_factory=TestingSession, sender=sender) == 1
        db = TestingSession()
        try:
            row = db.get(SmsOutbox, response.json()["id"])
            assert row is not None
            assert row.status == "sent"
            assert row.provider_message_id == "sms-msg-1"
        finally:
            db.close()
    finally:
        settings.sms_provider = original["sms_provider"]
        settings.sms_api_url = original["sms_api_url"]
        settings.sms_from = original["sms_from"]
