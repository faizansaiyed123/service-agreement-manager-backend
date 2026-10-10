from datetime import UTC, date, datetime, timedelta


def invoice_site(client, headers, email="invoice-customer@example.com"):
    customer_res = client.post("/api/v1/customers", headers=headers, json={
        "name": "Invoice Customer", "email": email,
    })
    assert customer_res.status_code == 201, customer_res.text
    customer = customer_res.json()
    location_res = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Billing Site", "address_line1": "50 Commerce Way", "city": "Austin",
    })
    assert location_res.status_code == 201, location_res.text
    return customer, location_res.json()


def invoice_payload(customer, location, due_date=None):
    today = datetime.now(UTC).date()
    return {
        "customer_id": customer["id"], "service_location_id": location["id"],
        "invoice_date": today.isoformat(), "due_date": (due_date or today + timedelta(days=14)).isoformat(),
        "lines": [
            {"service_code": "LABOR", "description": "Maintenance labor", "quantity": "1.5", "unit_price": "40.00"},
            {"service_code": "FILTER", "description": "Replacement filter", "quantity": "2", "unit_price": "10.25"},
        ],
    }


def test_invoice_issue_payment_idempotency_and_history(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Billing HVAC", "full_name": "Billing Owner",
        "email": "billing-owner@example.com", "password": "correct-horse-battery-42",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    customer, location = invoice_site(client, headers)
    response = client.post("/api/v1/invoices", headers=headers, json=invoice_payload(customer, location))
    assert response.status_code == 201, response.text
    invoice = response.json()
    invoice_id = invoice["id"]
    assert invoice["invoice_number"] == "INV-000001"
    assert invoice["total_amount"] == "80.50"
    assert invoice["balance_due"] == "80.50"
    issued = client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers)
    assert issued.status_code == 200, issued.text
    assert issued.json()["status"] == "issued"

    payment_headers = {**headers, "Idempotency-Key": "billing-attempt-0001"}
    payment_payload = {"amount": "30.50", "payment_method": "bank_transfer", "reference": "BANK-REF-1"}
    first = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers=payment_headers, json=payment_payload)
    assert first.status_code == 201, first.text
    replay = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers=payment_headers, json=payment_payload)
    assert replay.status_code == 200, replay.text
    assert replay.json()["id"] == first.json()["id"]
    summary = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    assert summary["status"] == "partially_paid"
    assert summary["amount_paid"] == "30.50"
    assert summary["balance_due"] == "50.00"

    mismatch = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers=payment_headers, json={
        "amount": "31.00", "payment_method": "bank_transfer", "reference": "BANK-REF-1",
    })
    assert mismatch.status_code == 409
    overpayment = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers={
        **headers, "Idempotency-Key": "billing-attempt-0002",
    }, json={"amount": "50.01", "payment_method": "bank_transfer"})
    assert overpayment.status_code == 409

    final_payment = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers={
        **headers, "Idempotency-Key": "billing-attempt-0003",
    }, json={"amount": "50.00", "payment_method": "check"})
    assert final_payment.status_code == 201, final_payment.text
    settled = client.get(f"/api/v1/invoices/{invoice_id}", headers=headers).json()
    assert settled["status"] == "paid"
    assert settled["amount_paid"] == "80.50"
    assert settled["balance_due"] == "0.00"
    assert client.patch(f"/api/v1/invoices/{invoice_id}", headers=headers, json={"notes": "must not change"}).status_code == 409
    events = client.get(f"/api/v1/invoices/{invoice_id}/events", headers=headers)
    assert events.status_code == 200
    assert [item["event_type"] for item in events.json()] == [
        "invoice.created", "invoice.issued", "invoice.payment_recorded", "invoice.payment_recorded"
    ]


def test_invoice_void_overdue_filter_and_tenant_isolation(client):
    owner = client.post("/api/v1/auth/register", json={
        "company_name": "Tenant Billing", "full_name": "Tenant Owner",
        "email": "tenant-billing@example.com", "password": "correct-horse-battery-42",
    }).json()
    stranger = client.post("/api/v1/auth/register", json={
        "company_name": "Other Billing", "full_name": "Other Owner",
        "email": "other-billing@example.com", "password": "correct-horse-battery-43",
    }).json()
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    other_headers = {"Authorization": f"Bearer {stranger['access_token']}"}
    customer, location = invoice_site(client, headers)
    overdue_date = datetime.now(UTC).date() - timedelta(days=1)
    payload = invoice_payload(customer, location, due_date=datetime.now(UTC).date())
    payload["invoice_date"] = overdue_date.isoformat()
    payload["due_date"] = overdue_date.isoformat()
    created = client.post("/api/v1/invoices", headers=headers, json=payload)
    assert created.status_code == 201, created.text
    invoice_id = created.json()["id"]
    assert client.get(f"/api/v1/invoices/{invoice_id}", headers=other_headers).status_code == 404
    assert client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers).status_code == 200
    assert client.get("/api/v1/invoices?status=overdue", headers=headers).json()[0]["is_overdue"] is True

    draft = client.post("/api/v1/invoices", headers=headers, json=invoice_payload(customer, location))
    assert draft.status_code == 201
    voided = client.post(f"/api/v1/invoices/{draft.json()['id']}/void", headers=headers, json={"reason": "Created by mistake"})
    assert voided.status_code == 200
    assert voided.json()["status"] == "void"
    assert client.post(f"/api/v1/invoices/{draft.json()['id']}/issue", headers=headers).status_code == 409
