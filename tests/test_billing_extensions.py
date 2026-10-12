from datetime import date, timedelta

from conftest import TestingSession
from app.workers.billing import run_once as run_recurring_once


def test_invoice_tax_discount_refund_credit_and_pdf(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Billing Extensions HVAC",
        "full_name": "Billing Extensions Owner",
        "email": "billing-extensions@example.com",
        "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    customer = client.post("/api/v1/customers", headers=headers, json={"name": "Adjustment Customer"}).json()
    location = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Adjustment Site", "address_line1": "1 Billing Way", "city": "Austin"},
    ).json()
    payload = {
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "invoice_date": date.today().isoformat(),
        "due_date": (date.today() + timedelta(days=14)).isoformat(),
        "discount_percent": "10.00",
        "tax_percent": "20.00",
        "lines": [{"service_code": "LABOR", "description": "Labor", "quantity": "1", "unit_price": "100.00"}],
    }
    created = client.post("/api/v1/invoices", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    invoice = created.json()
    assert invoice["discount_amount"] == "10.00"
    assert invoice["tax_amount"] == "18.00"
    assert invoice["total_amount"] == "108.00"

    invoice_id = invoice["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers).status_code == 200
    payment = client.post(
        f"/api/v1/invoices/{invoice_id}/payments",
        headers={**headers, "Idempotency-Key": "adjust-payment-001"},
        json={"amount": "108.00", "payment_method": "bank_transfer"},
    )
    assert payment.status_code == 201, payment.text
    payment_id = payment.json()["id"]

    refund = client.post(
        f"/api/v1/invoices/{invoice_id}/payments/{payment_id}/refunds",
        headers={**headers, "Idempotency-Key": "adjust-refund-001"},
        json={"amount": "20.00", "refund_method": "bank_transfer", "reason": "Customer refund"},
    )
    assert refund.status_code == 201, refund.text
    after_refund = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    assert after_refund["amount_paid"] == "88.00"
    assert after_refund["amount_refunded"] == "20.00"
    assert after_refund["balance_due"] == "20.00"

    credit = client.post(
        f"/api/v1/invoices/{invoice_id}/credits",
        headers={**headers, "Idempotency-Key": "adjust-credit-001"},
        json={"amount": "8.00", "reason": "Goodwill credit"},
    )
    assert credit.status_code == 201, credit.text
    after_credit = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    assert after_credit["credits_applied"] == "8.00"
    assert after_credit["balance_due"] == "12.00"

    pdf = client.get(f"/api/v1/invoices/{invoice_id}/pdf", headers=headers)
    assert pdf.status_code == 200, pdf.text
    assert pdf.headers["content-type"].startswith("application/pdf")
    assert pdf.content.startswith(b"%PDF")


def test_recurring_invoice_schedule_generates_and_advances(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Recurring HVAC",
        "full_name": "Recurring Owner",
        "email": "recurring@example.com",
        "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    customer = client.post("/api/v1/customers", headers=headers, json={"name": "Recurring Customer"}).json()
    location = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={"name": "Recurring Site", "address_line1": "1 Recurring Way", "city": "Dallas"},
    ).json()
    schedule = client.post("/api/v1/recurring-invoices", headers=headers, json={
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "name": "Monthly maintenance",
        "frequency": "monthly",
        "next_invoice_date": date.today().isoformat(),
        "due_days": 15,
        "auto_issue": True,
        "lines": [{"service_code": "MAINT", "description": "Monthly maintenance", "quantity": "1", "unit_price": "250.00"}],
    })
    assert schedule.status_code == 201, schedule.text

    assert run_recurring_once(session_factory=TestingSession) >= 1
    invoices = client.get("/api/v1/invoices", headers=headers).json()
    assert len(invoices) == 1
    assert invoices[0]["status"] == "issued"
    assert invoices[0]["total_amount"] == "250.00"

    refreshed = client.get(f"/api/v1/recurring-invoices/{schedule.json()['id']}", headers=headers)
    assert refreshed.status_code == 200
    assert refreshed.json()["last_invoice_id"] == invoices[0]["id"]
    assert refreshed.json()["next_invoice_date"] != date.today().isoformat()
