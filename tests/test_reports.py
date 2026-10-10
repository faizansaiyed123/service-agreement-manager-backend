from datetime import UTC, datetime, timedelta


def register_user(client, email):
    result = client.post("/api/v1/auth/register", json={
        "company_name": "Reports HVAC", "full_name": "Reports Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert result.status_code == 201, result.text
    return result.json()


def site(client, headers):
    customer = client.post("/api/v1/customers", headers=headers, json={"name": "Report Customer"})
    assert customer.status_code == 201
    location = client.post(f"/api/v1/customers/{customer.json()['id']}/service-locations", headers=headers, json={
        "name": "Report Site", "address_line1": "4 Report Street", "city": "Austin",
    })
    assert location.status_code == 201
    return customer.json(), location.json()


def test_receivables_report_calculates_partial_and_overdue_balances(client):
    user = register_user(client, "report-billing@example.com")
    headers = {"Authorization": f"Bearer {user['access_token']}"}
    customer, location = site(client, headers)
    today = datetime.now(UTC).date()
    invoice = client.post("/api/v1/invoices", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "invoice_date": (today - timedelta(days=10)).isoformat(),
        "due_date": (today - timedelta(days=2)).isoformat(),
        "lines": [{"service_code": "LABOR", "description": "Service labor", "quantity": "1", "unit_price": "100.00"}],
    })
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers).status_code == 200
    payment = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers={
        **headers, "Idempotency-Key": "report-payment-0001",
    }, json={"amount": "30.00", "payment_method": "check"})
    assert payment.status_code == 201

    report = client.get("/api/v1/reports/billing/receivables", headers=headers)
    assert report.status_code == 200, report.text
    data = report.json()
    assert data["issued_invoice_count"] == 1
    assert data["total_invoiced"] == "100.00"
    assert data["total_paid"] == "30.00"
    assert data["outstanding"] == "70.00"
    assert data["overdue_invoice_count"] == 1
    assert data["overdue_amount"] == "70.00"


def test_reports_are_tenant_scoped_and_dates_validated(client):
    first = register_user(client, "reports-one@example.com")
    second = register_user(client, "reports-two@example.com")
    first_headers = {"Authorization": f"Bearer {first['access_token']}"}
    second_headers = {"Authorization": f"Bearer {second['access_token']}"}
    customer, location = site(client, first_headers)
    today = datetime.now(UTC).date()
    created = client.post("/api/v1/work-orders", headers=first_headers, json={
        "customer_id": customer["id"], "service_location_id": location["id"],
        "title": "Inspection", "scheduled_for": (today - timedelta(days=2)).isoformat(),
        "priority": "high",
    })
    assert created.status_code == 201, created.text
    first_report = client.get("/api/v1/reports/work-orders", headers=first_headers)
    second_report = client.get("/api/v1/reports/work-orders", headers=second_headers)
    assert first_report.status_code == 200
    assert first_report.json()["status_counts"]["scheduled"] == 1
    assert first_report.json()["overdue_open_count"] == 1
    assert second_report.status_code == 200
    assert second_report.json()["status_counts"] == {}
    assert client.get("/api/v1/reports/billing/receivables?invoice_date_from=2026-12-01&invoice_date_to=2026-01-01", headers=first_headers).status_code == 422
