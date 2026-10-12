from io import BytesIO

import pytest

from app.core.storage import LocalStorage
from app.workers.webhooks import WebhookDeliveryError, sign_payload, validate_target


def test_local_storage_rejects_path_escape_and_round_trips(tmp_path):
    storage = LocalStorage(str(tmp_path), 1024)
    size, digest = storage.save_stream(BytesIO(b"hello"), "company/entity/object")
    assert size == 5
    assert storage.exists("company/entity/object")
    assert storage.open("company/entity/object").read() == b"hello"
    assert len(digest) == 64
    with pytest.raises(ValueError):
        storage.exists("../escape")


def test_local_storage_enforces_size_limit(tmp_path):
    storage = LocalStorage(str(tmp_path), 3)
    with pytest.raises(ValueError):
        storage.save_stream(BytesIO(b"toolong"), "company/file")


def test_webhook_signing_and_private_target_protection():
    body = b'{"hello":"world"}'
    signature = sign_payload(body, "secret", 123)
    assert signature.startswith("v1=")

    with pytest.raises(WebhookDeliveryError):
        validate_target("http://example.com")
    with pytest.raises(WebhookDeliveryError):
        validate_target("https://127.0.0.1")
    with pytest.raises(WebhookDeliveryError):
        validate_target("https://localhost")
