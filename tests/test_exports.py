import csv
import io
from datetime import UTC, datetime, timedelta


def owner(client, email, company="Export HVAC"):
    result = client.post("/api/v1/auth/register", json={
        "company_name": company, "full_name": "Export Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert result.status_code == 201, result.text
    return {"Authorization": f"Bearer {result.json()['access_token']}"}


def create_customer(client, headers, name):
    response = client.post("/api/v1/customers", headers=headers, json={"name": name})
    assert response.status_code == 201, response.text
    return response.json()


def rows(content):
    return list(csv.reader(io.StringIO(content)))


def test_customer_csv_export_tenant_scope_and_formula_neutralization(client):
    headers = owner(client, "export-owner@example.com")
    other_headers = owner(client, "other-export-owner@example.com", "Other Export HVAC")
    created = create_customer(client, headers, "=HYPERLINK(\"https://evil.example\",\"click\")")
    create_customer(client, other_headers, "Private Customer")

    response = client.get("/api/v1/exports/customers.csv", headers=headers)
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")
    assert 'attachment; filename="customers.csv"' in response.headers["content-disposition"]
    data = rows(response.text)
    assert len(data) == 2
    assert data[1][0] == created["id"]
    assert data[1][3].startswith("'=")
    assert "Private Customer" not in response.text

    assert client.get("/api/v1/exports/customers.csv?limit=10001", headers=headers).status_code == 422
    assert client.get("/api/v1/exports/customers.csv?created_from=2026-12-01&created_to=2026-01-01", headers=headers).status_code == 422


def test_invoice_export_includes_ledger_paid_and_balance(client):
    headers = owner(client, "export-invoices@example.com")
    customer = create_customer(client, headers, "Invoice Export Customer")
    location = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Billing Site", "address_line1": "10 Market Rd", "city": "Austin",
    })
    assert location.status_code == 201
    today = datetime.now(UTC).date()
    invoice = client.post("/api/v1/invoices", headers=headers, json={
        "customer_id": customer["id"], "service_location_id": location.json()["id"],
        "invoice_date": today.isoformat(), "due_date": (today + timedelta(days=7)).isoformat(),
        "lines": [{"service_code": "LABOR", "description": "Installation service", "quantity": "1", "unit_price": "125.00"}],
    })
    assert invoice.status_code == 201, invoice.text
    invoice_id = invoice.json()["id"]
    assert client.post(f"/api/v1/invoices/{invoice_id}/issue", headers=headers).status_code == 200
    payment = client.post(f"/api/v1/invoices/{invoice_id}/payments", headers={
        **headers, "Idempotency-Key": "export-payment-0001",
    }, json={"amount": "25.00", "payment_method": "check"})
    assert payment.status_code == 201
    data = rows(client.get("/api/v1/exports/invoices.csv", headers=headers).text)
    assert data[0][-3:] == ["total_amount", "amount_paid", "balance_due"]
    assert data[1][-3:] == ["125.00", "25.00", "100.00"]
