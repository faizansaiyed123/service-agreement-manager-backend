import os
from concurrent.futures import ThreadPoolExecutor
from datetime import UTC, date, datetime

import pytest
from fastapi import Response
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, func, select
from sqlalchemy.orm import sessionmaker

from app.api.billing import record_payment
from app.api.deps import get_db
from app.core.errors import DomainError
from app.models import Payment, User, WorkOrder
from app.schemas.billing import PaymentCreate
from app.services.maintenance import generate_scheduled_occurrence
from app.main import app

PG_URL = os.environ.get("SAM_ORIGINAL_DATABASE_URL", "")
RUN_RACE = os.environ.get("RUN_PG_RACE_TESTS") == "1"

pytestmark = pytest.mark.skipif(
    not RUN_RACE or not PG_URL.startswith("postgresql"),
    reason="PostgreSQL concurrency suite requires RUN_PG_RACE_TESTS=1 and a PostgreSQL DATABASE_URL",
)


@pytest.fixture(scope="module")
def pg_session_factory():
    engine = create_engine(PG_URL, pool_pre_ping=True, future=True)
    factory = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    yield factory
    engine.dispose()


@pytest.fixture()
def pg_client(pg_session_factory):
    def override_get_db():
        db = pg_session_factory()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = override_get_db
    try:
        with TestClient(app) as client:
            yield client
    finally:
        app.dependency_overrides.clear()


def register(pg_client, email: str):
    response = pg_client.post("/api/v1/auth/register", json={
        "company_name": f"Race Test {email}",
        "full_name": "Race Test Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_concurrent_invoice_payments_serialize_on_postgresql(pg_session_factory, pg_client):
    headers = register(pg_client, "race-payments@example.com")
    customer_res = pg_client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Race Payment Customer", "email": "race-payment-customer@example.com"},
    )
    assert customer_res.status_code == 201, customer_res.text
    customer = customer_res.json()
    location_res = pg_client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Race Site", "address_line1": "1 Lock Street", "city": "Austin"},
    )
    assert location_res.status_code == 201, location_res.text
    location = location_res.json()

    invoice_res = pg_client.post(
        "/api/v1/invoices",
        headers=headers,
        json={
            "customer_id": customer["id"],
            "service_location_id": location["id"],
            "invoice_date": date.today().isoformat(),
            "due_date": date.today().isoformat(),
            "lines": [{
                "service_code": "RACE",
                "description": "Concurrency test",
                "quantity": "1",
                "unit_price": "100.00",
            }],
        },
    )
    assert invoice_res.status_code == 201, invoice_res.text
    invoice_id = invoice_res.json()["id"]
    issued = pg_client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers)
    assert issued.status_code == 200, issued.text

    session = pg_session_factory()
    try:
        user = session.scalar(select(User).where(User.email == "race-payments@example.com"))
    finally:
        session.close()
    assert user is not None

    def attempt(key: str):
        db = pg_session_factory()
        try:
            fresh_user = db.get(User, user.id)
            payload = PaymentCreate(amount="80.00", payment_method="bank_transfer", reference=key)
            try:
                payment = record_payment(
                    invoice_id=invoice_id,
                    payload=payload,
                    response=Response(),
                    idempotency_key=key,
                    user=fresh_user,
                    db=db,
                )
                return ("success", str(payment.id))
            except DomainError as exc:
                db.rollback()
                return ("error", exc.code)
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(attempt, ["race-payment-001", "race-payment-002"]))

    assert sorted(result[0] for result in results) == ["error", "success"]
    assert next(result[1] for result in results if result[0] == "error") == "overpayment"

    db = pg_session_factory()
    try:
        paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(
            Payment.invoice_id == invoice_id
        ))
        assert str(paid) == "80.00"
    finally:
        db.close()


def test_concurrent_maintenance_generation_creates_one_occurrence(pg_session_factory, pg_client):
    headers = register(pg_client, "race-maintenance@example.com")
    customer_res = pg_client.post(
        "/api/v1/customers",
        headers=headers,
        json={"name": "Race Maintenance Customer"},
    )
    assert customer_res.status_code == 201, customer_res.text
    customer = customer_res.json()
    location_res = pg_client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Race Maintenance Site", "address_line1": "2 Lock Street", "city": "Austin"},
    )
    assert location_res.status_code == 201, location_res.text
    location = location_res.json()

    today = datetime.now(UTC).date()
    schedule_res = pg_client.post(
        "/api/v1/maintenance/schedules",
        headers=headers,
        json={
            "customer_id": customer["id"],
            "service_location_id": location["id"],
            "name": "Race Maintenance",
            "frequency": "monthly",
            "next_due_date": today.isoformat(),
            "checklist_template": [],
        },
    )
    assert schedule_res.status_code == 201, schedule_res.text
    schedule_id = schedule_res.json()["id"]

    db = pg_session_factory()
    try:
        user = db.scalar(select(User).where(User.email == "race-maintenance@example.com"))
    finally:
        db.close()
    assert user is not None

    def generate():
        db = pg_session_factory()
        try:
            order, created = generate_scheduled_occurrence(
                db,
                user.company_id,
                schedule_id,
                today,
                user.id,
                today=today,
            )
            db.commit()
            return (str(order.id), created)
        except Exception:
            db.rollback()
            raise
        finally:
            db.close()

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(lambda _: generate(), range(2)))

    assert sorted(result[1] for result in results) == [False, True]
    assert len({result[0] for result in results}) == 1

    db = pg_session_factory()
    try:
        orders = list(db.scalars(select(WorkOrder).where(
            WorkOrder.maintenance_schedule_id == schedule_id,
            WorkOrder.occurrence_date == today,
        )).all())
        assert len(orders) == 1
    finally:
        db.close()
