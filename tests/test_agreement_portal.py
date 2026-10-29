import re
from datetime import UTC, datetime, timedelta
from uuid import UUID

from conftest import TestingSession
from app.models import AgreementPortalToken, NotificationOutbox


def register_owner(client, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": "Portal HVAC", "full_name": "Portal Owner",
        "email": email, "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return response.json()


def create_proposed_agreement(client, headers, *, email="customer@example.com", title="Portal Agreement"):
    customer = client.post("/api/v1/customers", headers=headers, json={
        "name": "Portal Customer", "email": email,
    }).json()
    location = client.post(f"/api/v1/customers/{customer['id']}/service-locations", headers=headers, json={
        "name": "Main Site", "address_line1": "10 Service Road", "city": "Austin",
    }).json()
    agreement = client.post("/api/v1/agreements", headers=headers, json={
        "customer_id": customer["id"],
        "service_location_id": location["id"],
        "title": title,
        "start_date": datetime.now(UTC).date().isoformat(),
        "end_date": (datetime.now(UTC).date() + timedelta(days=365)).isoformat(),
        "billing_frequency": "annual",
        "terms_text": "Two planned visits.",
        "lines": [{"name": "Annual maintenance", "service_code": "MAINT", "quantity": "1", "unit_price": "1000.00"}],
    })
    assert agreement.status_code == 201, agreement.text
    proposed = client.post(f"/api/v1/agreements/{agreement.json()['id']}/propose", headers=headers)
    assert proposed.status_code == 200, proposed.text
    return proposed.json()


def token_from_notification(client, notification_id, headers):
    notification = client.get(f"/api/v1/notifications/{notification_id}", headers=headers)
    assert notification.status_code == 200, notification.text
    match = re.search(r"https?://[^\s]+/agreement/([^\s]+)", notification.json()["body"])
    assert match, notification.json()["body"]
    return match.group(1)


def test_customer_acceptance_is_automatic_and_idempotent(client):
    owner = register_owner(client, "portal-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    agreement = create_proposed_agreement(client, headers)

    sent = client.post(f"/api/v1/agreement-portal/agreements/{agreement['id']}/send", headers=headers, json={})
    assert sent.status_code == 200, sent.text
    assert sent.json()["notification_status"] == "queued"
    token = token_from_notification(client, sent.json()["notification_id"], headers)

    public = client.get(f"/api/v1/agreement-portal/public/{token}")
    assert public.status_code == 200, public.text
    assert public.json()["portal_status"] == "pending"
    assert public.json()["agreement_number"] == agreement["agreement_number"]

    accepted = client.post(f"/api/v1/agreement-portal/public/{token}/respond", json={"decision": "accept"})
    assert accepted.status_code == 200, accepted.text
    assert accepted.json()["portal_status"] == "accepted"
    assert accepted.json()["accepted_at"]
    assert accepted.json()["rejection_reason"] is None

    stored = client.get(f"/api/v1/agreements/{agreement['id']}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["status"] == "active"
    assert stored.json()["acceptance_method"] == "electronic"
    assert stored.json()["accepted_by_name"] == "Portal Customer"
    assert stored.json()["acceptance_reference"].startswith("portal:")

    replay = client.post(f"/api/v1/agreement-portal/public/{token}/respond", json={"decision": "accept"})
    assert replay.status_code == 200, replay.text
    assert replay.json()["portal_status"] == "accepted"
    opposite = client.post(f"/api/v1/agreement-portal/public/{token}/respond", json={"decision": "reject"})
    assert opposite.status_code == 409


def test_customer_rejection_creates_distinct_rejected_state(client):
    owner = register_owner(client, "portal-reject-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    agreement = create_proposed_agreement(client, headers, title="Rejectable Agreement")
    sent = client.post(f"/api/v1/agreement-portal/agreements/{agreement['id']}/send", headers=headers, json={})
    token = token_from_notification(client, sent.json()["notification_id"], headers)

    rejected = client.post(
        f"/api/v1/agreement-portal/public/{token}/respond",
        json={"decision": "reject", "rejection_reason": "The quoted price is not approved."},
    )
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["portal_status"] == "rejected"
    assert rejected.json()["rejection_reason"] == "The quoted price is not approved."

    stored = client.get(f"/api/v1/agreements/{agreement['id']}", headers=headers)
    assert stored.status_code == 200
    assert stored.json()["status"] == "rejected"
    assert stored.json()["rejected_by_name"] == "Portal Customer"
    assert stored.json()["rejection_reason"] == "The quoted price is not approved."

    listed = client.get("/api/v1/agreements?status=rejected", headers=headers)
    assert listed.status_code == 200
    assert [item["id"] for item in listed.json()] == [agreement["id"]]


def test_resend_revokes_previous_link_and_expired_links_cannot_be_used(client):
    owner = register_owner(client, "portal-resend-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    agreement = create_proposed_agreement(client, headers, title="Resend Agreement")

    first = client.post(f"/api/v1/agreement-portal/agreements/{agreement['id']}/send", headers=headers, json={})
    first_token = token_from_notification(client, first.json()["notification_id"], headers)

    db = TestingSession()
    try:
        token_row = db.scalar(AgreementPortalToken)
        token_row.sent_at = datetime.now(UTC) - timedelta(minutes=10)
        db.commit()
    finally:
        db.close()

    second = client.post(f"/api/v1/agreement-portal/agreements/{agreement['id']}/send", headers=headers, json={})
    assert second.status_code == 200, second.text
    second_token = token_from_notification(client, second.json()["notification_id"], headers)
    assert second_token != first_token

    old_link = client.get(f"/api/v1/agreement-portal/public/{first_token}")
    assert old_link.status_code == 410

    db = TestingSession()
    try:
        token_rows = list(db.query(AgreementPortalToken).filter(AgreementPortalToken.agreement_id == UUID(agreement["id"])).all())
        assert {row.status for row in token_rows} == {"revoked", "pending"}
    finally:
        db.close()

    expired = client.get(f"/api/v1/agreement-portal/public/{second_token}")
    assert expired.status_code == 200
    db = TestingSession()
    try:
        current = db.query(AgreementPortalToken).filter(AgreementPortalToken.token_hash.isnot(None)).order_by(AgreementPortalToken.sent_at.desc()).first()
        current.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        db.commit()
    finally:
        db.close()
    assert client.get(f"/api/v1/agreement-portal/public/{second_token}").status_code == 410


def test_send_requires_recipient_email_and_only_customer_contacts(client):
    owner = register_owner(client, "portal-recipient-owner@example.com")
    headers = {"Authorization": f"Bearer {owner['access_token']}"}
    agreement = create_proposed_agreement(client, headers, email=None, title="Missing Email")
    missing = client.post(f"/api/v1/agreement-portal/agreements/{agreement['id']}/send", headers=headers, json={})
    assert missing.status_code == 422

    other_customer = client.post("/api/v1/customers", headers=headers, json={"name": "Other Customer", "email": "other@example.com"}).json()
    forged_contact = UUID(other_customer["id"])
    invalid_contact = client.post(
        f"/api/v1/agreement-portal/agreements/{agreement['id']}/send",
        headers=headers,
        json={"contact_id": str(forged_contact)},
    )
    assert invalid_contact.status_code == 404
