import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class WebhookSecretError(ValueError):
    pass


def _fernet(master_key: str) -> Fernet:
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_secret(secret: str, master_key: str) -> str:
    return _fernet(master_key).encrypt(secret.encode("utf-8")).decode("ascii")


def decrypt_secret(ciphertext: str, master_key: str) -> str:
    try:
        return _fernet(master_key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
        raise WebhookSecretError("Webhook secret could not be decrypted") from exc
