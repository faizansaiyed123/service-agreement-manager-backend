import re
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from uuid import UUID

from sqlalchemy import select

from conftest import TestingSession
from app.models import InvoicePortalToken, NotificationOutbox


def register_owner(client, email="invoice-portal-owner@example.com"):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Invoice Portal HVAC",
        "full_name": "Invoice Portal Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def create_invoice(client, headers, *, email="customer@example.com", issue=True):
    customer_response = client.post("/api/v1/customers", headers=headers, json={
        "name": "Portal Customer",
        "email": email,
    })
    assert customer_response.status_code == 201, customer_response.text
    customer = customer_response.json()
    location_response = client.post(
        f"/api/v1/customers/{customer['id']}/service-locations",
        headers=headers,
        json={
            "name": "Main Site",
            "address_line1": "10 Service Road",
            "city": "Austin",
        },
    )
    assert location_response.status_code == 201, location_response.text
    location = location_response.json()

    response = client.post("/api/v1/invoices", headers=headers, json={
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "invoice_date": datetime.now(UTC).date().isoformat(),
        "due_date": (datetime.now(UTC).date() + timedelta(days=14)).isoformat(),
        "discount_percent": "20.00",
        "tax_percent": "3.00",
        "lines": [{
            "service_code": "SERVICE",
            "description": "Service visit",
            "quantity": "1",
            "unit_price": "220.00",
        }],
    })
    assert response.status_code == 201, response.text
    invoice = response.json()
    assert invoice["subtotal"] == "220.00"
    assert invoice["discount_amount"] == "44.00"
    assert invoice["tax_amount"] == "5.28"
    assert invoice["total_amount"] == "181.28"
    if issue:
        issued = client.post(f"/api/v1/invoices/{invoice['id']}/issue", headers=headers)
        assert issued.status_code == 200, issued.text
        invoice = issued.json()
    return invoice, customer


def send_link(client, headers, invoice_id):
    response = client.post(
        f"/api/v1/invoice-portal/invoices/{invoice_id}/send",
        headers=headers,
        json={},
    )
    assert response.status_code == 200, response.text
    return response.json()


def token_from_notification(client, headers, notification_id):
    notification = client.get(f"/api/v1/notifications/{notification_id}", headers=headers)
    assert notification.status_code == 200, notification.text
    links = [line.strip() for line in notification.json()["body"].splitlines() if line.strip().startswith("http") and "/invoice/" in line]
    assert links, notification.json()["body"]
    return links[0].rsplit("/invoice/", 1)[1]


def test_invoice_payment_link_exposes_correct_invoice_and_stores_only_token_hash(client):
    headers = register_owner(client)
    invoice, _ = create_invoice(client, headers)
    sent = send_link(client, headers, invoice["id"])
    assert sent["notification_status"] == "queued"
    assert sent["recipient_email"] == "customer@example.com"
    assert sent["balance_due"] == "181.28"

    token = token_from_notification(client, headers, sent["notification_id"])
    public = client.get(f"/api/v1/invoice-portal/public/{token}")
    assert public.status_code == 200, public.text
    assert public.headers["cache-control"] == "no-store"
    assert public.headers["referrer-policy"] == "no-referrer"
    body = public.json()
    assert body["invoice_number"] == invoice["invoice_number"]
    assert body["subtotal"] == "220.00"
    assert body["discount_amount"] == "44.00"
    assert body["tax_amount"] == "5.28"
    assert body["total_amount"] == "181.28"
    assert body["balance_due"] == "181.28"
    assert body["portal_status"] == "payable"

    db = TestingSession()
    try:
        record = db.scalar(select(InvoicePortalToken).where(InvoicePortalToken.invoice_id == UUID(invoice["id"])))
        assert record is not None
        assert record.token_hash != token
    finally:
        db.close()


def test_customer_payment_intent_uses_server_calculated_outstanding_balance(client, monkeypatch):
    headers = register_owner(client, "partial-payment-owner@example.com")
    invoice, _ = create_invoice(client, headers)
    partial = client.post(
        f"/api/v1/invoices/{invoice['id']}/payments",
        headers={**headers, "Idempotency-Key": "offline-partial-payment-1"},
        json={"amount": "20.00", "payment_method": "bank_transfer"},
    )
    assert partial.status_code == 201, partial.text

    sent = send_link(client, headers, invoice["id"])
    token = token_from_notification(client, headers, sent["notification_id"])
    observed = {}

    monkeypatch.setattr("app.services.stripe_service.stripe_enabled", lambda: True)

    def fake_create_payment_intent(invoice, *, amount_due, idempotency_key, invoice_portal_token_id=None):
        observed.update({
            "amount_due": amount_due,
            "idempotency_key": idempotency_key,
            "invoice_portal_token_id": invoice_portal_token_id,
        })
        return {
            "payment_intent_id": "pi_test_outstanding",
            "client_secret": "pi_test_outstanding_secret",
            "amount": str(amount_due),
            "currency": invoice.currency,
            "test_mode": True,
        }

    monkeypatch.setattr("app.services.stripe_service.create_payment_intent", fake_create_payment_intent)
    response = client.post(
        f"/api/v1/invoice-portal/public/{token}/payment-intent",
        json={},
    )
    assert response.status_code == 200, response.text
    assert response.json()["amount"] == "161.28"
    assert response.json()["test_mode"] is True
    assert observed["amount_due"] == Decimal("161.28")
    assert observed["invoice_portal_token_id"] is not None
    assert observed["idempotency_key"].startswith("invoice-portal:")


def test_payment_links_reject_drafts_and_customers_without_email(client):
    headers = register_owner(client, "invalid-payment-link-owner@example.com")
    draft, _ = create_invoice(client, headers, email="draft-customer@example.com", issue=False)
    not_issued = client.post(
        f"/api/v1/invoice-portal/invoices/{draft['id']}/send",
        headers=headers,
        json={},
    )
    assert not_issued.status_code == 409

    issued, _ = create_invoice(client, headers, email=None, issue=True)
    missing_email = client.post(
        f"/api/v1/invoice-portal/invoices/{issued['id']}/send",
        headers=headers,
        json={},
    )
    assert missing_email.status_code == 422
    assert missing_email.json()["error"]["code"] == "recipient_email_missing"


def test_resending_payment_link_revokes_old_token_and_expiration_is_enforced(client):
    headers = register_owner(client, "resend-payment-link-owner@example.com")
    invoice, _ = create_invoice(client, headers)
    first = send_link(client, headers, invoice["id"])
    first_token = token_from_notification(client, headers, first["notification_id"])

    db = TestingSession()
    try:
        row = db.scalar(select(InvoicePortalToken).where(InvoicePortalToken.invoice_id == UUID(invoice["id"])))
        row.sent_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    second = send_link(client, headers, invoice["id"])
    second_token = token_from_notification(client, headers, second["notification_id"])
    assert first_token != second_token
    assert client.get(f"/api/v1/invoice-portal/public/{first_token}").status_code == 410

    db = TestingSession()
    try:
        row = db.scalar(select(InvoicePortalToken).where(InvoicePortalToken.token_hash.isnot(None)).order_by(InvoicePortalToken.sent_at.desc()))
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    expired = client.get(f"/api/v1/invoice-portal/public/{second_token}")
    assert expired.status_code == 410
    assert expired.json()["error"]["code"] == "invoice_link_expired"


def test_payment_confirmation_rejects_an_intent_for_a_different_invoice(client, monkeypatch):
    headers = register_owner(client, "wrong-intent-owner@example.com")
    invoice, _ = create_invoice(client, headers)
    sent = send_link(client, headers, invoice["id"])
    token = token_from_notification(client, headers, sent["notification_id"])

    class FakePaymentIntent:
        @staticmethod
        def retrieve(_payment_intent_id):
            return {
                "id": "pi_wrong_invoice",
                "status": "succeeded",
                "amount": 18128,
                "amount_received": 18128,
                "currency": "usd",
                "metadata": {
                    "invoice_id": "00000000-0000-0000-0000-000000000000",
                    "company_id": invoice["company_id"],
                    "invoice_portal_token_id": "wrong-token",
                },
            }

    class FakeStripeClient:
        PaymentIntent = FakePaymentIntent

    monkeypatch.setattr("app.services.stripe_service._client", lambda: FakeStripeClient())
    response = client.post(
        f"/api/v1/invoice-portal/public/{token}/confirm",
        json={"payment_intent_id": "pi_wrong_invoice"},
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "payment_intent_not_found"


def test_technicians_cannot_read_invoice_lists_or_send_customer_payment_links(client):
    headers = register_owner(client, "technician-billing-scope-owner@example.com")
    invoice, _ = create_invoice(client, headers)
    branch_response = client.post("/api/v1/branches", headers=headers, json={
        "name": "Technician Test Branch",
        "code": "TECH-TEST",
        "timezone": "UTC",
        "country_code": "US",
        "is_primary": False,
    })
    assert branch_response.status_code == 201, branch_response.text
    invite = client.post("/api/v1/team/invitations", headers=headers, json={
        "full_name": "Limited Technician",
        "email": "limited-technician@example.com",
        "branch_ids": [branch_response.json()["id"]],
        "skills": ["HVAC"],
    })
    assert invite.status_code == 201, invite.text
    with TestingSession() as db:
        notification = db.scalar(select(NotificationOutbox).where(
            NotificationOutbox.recipient_email == "limited-technician@example.com",
            NotificationOutbox.event_type == "team.technician_invited",
        ).order_by(NotificationOutbox.created_at.desc(), NotificationOutbox.id.desc()).limit(1))
        assert notification is not None
        match = re.search(r"/team/invitation/([^\s/]+)", notification.body)
        assert match is not None, notification.body
        token = match.group(1).rstrip(".,)")
    accepted = client.post(f"/api/v1/team/invitations/public/{token}/accept", json={
        "password": "technician-password-42",
    })
    assert accepted.status_code == 201, accepted.text
    tech_headers = {"Authorization": f"Bearer {accepted.json()['access_token']}"}

    assert client.get("/api/v1/invoices", headers=tech_headers).status_code == 403
    assert client.get(f"/api/v1/invoices/{invoice['id']}", headers=tech_headers).status_code == 403
    assert client.post(
        f"/api/v1/invoice-portal/invoices/{invoice['id']}/send",
        headers=tech_headers,
        json={},
    ).status_code == 403
