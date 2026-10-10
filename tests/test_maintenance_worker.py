from datetime import UTC, date, datetime, timedelta
from uuid import UUID

from conftest import TestingSession
from sqlalchemy import select

from app.models import MaintenanceSchedule, WorkOrder
from app.services.maintenance import next_occurrence
from app.workers.maintenance import run_once


def register_owner(client, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Scheduled HVAC", "full_name": "Schedule Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def make_customer_and_location(client, headers, name):
    customer_response = client.post("/api/v1/customers", headers=headers, json={"name": name})
    assert customer_response.status_code == 201, customer_response.text
    customer = customer_response.json()
    location_response = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Main Site", "address_line1": "25 Maintenance Road", "city": "Austin"},
    )
    assert location_response.status_code == 201, location_response.text
    return customer, location_response.json()


def make_schedule(client, headers, customer, location, due_date, name="Monthly inspection"):
    response = client.post("/api/v1/maintenance/schedules", headers=headers, json={
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "name": name,
        "frequency": "monthly",
        "next_due_date": due_date.isoformat(),
        "checklist_template": ["Inspect filter", "Test thermostat"],
    })
    assert response.status_code == 201, response.text
    return response.json()


def test_worker_processes_due_schedules_retries_failures_and_skips_future(client):
    headers = register_owner(client, "maintenance-worker@example.com")
    today = datetime.now(UTC).date()
    inactive_customer, inactive_location = make_customer_and_location(client, headers, "Temporarily inactive")
    active_customer, active_location = make_customer_and_location(client, headers, "Active schedule customer")
    future_customer, future_location = make_customer_and_location(client, headers, "Future schedule customer")

    broken_schedule = make_schedule(client, headers, inactive_customer, inactive_location, today, "Retry after data repair")
    active_schedule = make_schedule(client, headers, active_customer, active_location, today, "Normal service")
    future_schedule = make_schedule(client, headers, future_customer, future_location, today + timedelta(days=1), "Future service")

    inactive = client.patch(f"/api/v1/customers/{inactive_customer['id']}", headers=headers, json={"status": "inactive"})
    assert inactive.status_code == 200, inactive.text

    result = run_once(TestingSession, as_of=today)
    assert result == {"scanned": 2, "generated": 1, "failed": 1, "skipped": 0}

    broken = client.get(f"/api/v1/maintenance/schedules/{broken_schedule['id']}", headers=headers).json()
    active = client.get(f"/api/v1/maintenance/schedules/{active_schedule['id']}", headers=headers).json()
    future = client.get(f"/api/v1/maintenance/schedules/{future_schedule['id']}", headers=headers).json()
    assert broken["last_generation_attempt_at"] is not None
    assert broken["last_generation_error"].startswith("customer_not_found:")
    assert broken["next_due_date"] == today.isoformat()
    assert active["last_generation_attempt_at"] is not None
    assert active["last_generation_error"] is None
    assert active["next_due_date"] == next_occurrence(today, "monthly").isoformat()
    assert future["last_generation_attempt_at"] is None

    work_orders = client.get("/api/v1/work-orders", headers=headers).json()
    assert len(work_orders) == 1
    assert work_orders[0]["maintenance_schedule_id"] == active_schedule["id"]

    restored = client.patch(f"/api/v1/customers/{inactive_customer['id']}", headers=headers, json={"status": "active"})
    assert restored.status_code == 200
    retry = run_once(TestingSession, as_of=today)
    assert retry == {"scanned": 1, "generated": 1, "failed": 0, "skipped": 0}
    recovered = client.get(f"/api/v1/maintenance/schedules/{broken_schedule['id']}", headers=headers).json()
    assert recovered["last_generation_error"] is None
    assert recovered["next_due_date"] == next_occurrence(today, "monthly").isoformat()
    assert len(client.get("/api/v1/work-orders", headers=headers).json()) == 2


def test_worker_catchup_is_bounded_and_occurrences_are_unique(client):
    headers = register_owner(client, "maintenance-catchup@example.com")
    customer, location = make_customer_and_location(client, headers, "Catch-up customer")
    today = datetime.now(UTC).date()
    old_due_date = today - timedelta(days=120)
    schedule = make_schedule(client, headers, customer, location, old_due_date, "Backlog service")

    result = run_once(
        TestingSession,
        as_of=today,
        max_occurrences_per_schedule=2,
    )
    assert result == {"scanned": 1, "generated": 2, "failed": 0, "skipped": 0}
    db = TestingSession()
    try:
        records = list(db.scalars(select(WorkOrder).where(
            WorkOrder.maintenance_schedule_id == UUID(schedule["id"])
        )).all())
        updated_schedule = db.get(MaintenanceSchedule, UUID(schedule["id"]))
        assert len(records) == 2
        assert len({record.occurrence_date for record in records}) == 2
        assert updated_schedule is not None
        assert updated_schedule.next_due_date > old_due_date
    finally:
        db.close()
