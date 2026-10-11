import hashlib

from app.core.config import get_settings


def register(client, company, email):
    response = client.post("/api/v1/auth/register", json={
        "company_name": company,
        "full_name": "Attachment Owner",
        "email": email,
        "password": "correct-horse-battery-42",
    })
    assert response.status_code == 201, response.text
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_attachment_upload_list_download_update_and_delete(client, tmp_path):
    settings = get_settings()
    original_root = settings.storage_root
    settings.storage_root = str(tmp_path)
    try:
        headers = register(client, "Attachment HVAC", "attachments@example.com")
        created = client.post(
            "/api/v1/customers",
            headers=headers,
            json={"name": "Attachment Customer", "email": "attachment@example.com"},
        )
        assert created.status_code == 201, created.text
        customer_id = created.json()["id"]
        content = b"service agreement attachment"
        checksum = hashlib.sha256(content).hexdigest()

        uploaded = client.post(
            f"/api/v1/attachments/customer/{customer_id}",
            headers=headers,
            files={"file": ("agreement.txt", content, "text/plain")},
            data={"description": "Signed service agreement"},
        )
        assert uploaded.status_code == 201, uploaded.text
        attachment = uploaded.json()
        assert attachment["entity_type"] == "customer"
        assert attachment["entity_id"] == customer_id
        assert attachment["size_bytes"] == len(content)
        assert attachment["sha256"] == checksum
        attachment_id = attachment["id"]

        listed = client.get(
            f"/api/v1/attachments?entity_type=customer&entity_id={customer_id}",
            headers=headers,
        )
        assert listed.status_code == 200
        assert [item["id"] for item in listed.json()] == [attachment_id]

        updated = client.patch(
            f"/api/v1/attachments/{attachment_id}",
            headers=headers,
            json={"description": "Updated agreement attachment"},
        )
        assert updated.status_code == 200
        assert updated.json()["description"] == "Updated agreement attachment"

        downloaded = client.get(f"/api/v1/attachments/{attachment_id}/download", headers=headers)
        assert downloaded.status_code == 200
        assert downloaded.content == content
        assert downloaded.headers["x-attachment-sha256"] == checksum

        deleted = client.delete(f"/api/v1/attachments/{attachment_id}", headers=headers)
        assert deleted.status_code == 200
        assert deleted.json()["status"] == "deleted"
        assert client.get(f"/api/v1/attachments/{attachment_id}", headers=headers).status_code == 404
        assert client.get(f"/api/v1/attachments/{attachment_id}/download", headers=headers).status_code == 404
    finally:
        settings.storage_root = original_root


def test_attachment_is_tenant_scoped_and_target_must_belong_to_company(client):
    first_headers = register(client, "Attachment Company One", "attachment-one@example.com")
    second_headers = register(client, "Attachment Company Two", "attachment-two@example.com")

    first_customer = client.post(
        "/api/v1/customers",
        headers=first_headers,
        json={"name": "First Customer"},
    )
    assert first_customer.status_code == 201, first_customer.text
    customer_id = first_customer.json()["id"]

    uploaded = client.post(
        f"/api/v1/attachments/customer/{customer_id}",
        headers=first_headers,
        files={"file": ("notes.txt", b"private", "text/plain")},
    )
    assert uploaded.status_code == 201, uploaded.text
    attachment_id = uploaded.json()["id"]

    cross_tenant = client.get(f"/api/v1/attachments/{attachment_id}", headers=second_headers)
    assert cross_tenant.status_code == 404

    cross_upload = client.post(
        f"/api/v1/attachments/customer/{customer_id}",
        headers=second_headers,
        files={"file": ("forbidden.txt", b"forbidden", "text/plain")},
    )
    assert cross_upload.status_code == 404
    assert cross_upload.json()["error"]["code"] == "attachment_entity_not_found"
