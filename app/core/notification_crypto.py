import base64
import hashlib

from cryptography.fernet import Fernet, InvalidToken


class SensitiveMessageError(ValueError):
    pass


def _fernet(master_key: str) -> Fernet:
    digest = hashlib.sha256(master_key.encode("utf-8")).digest()
    return Fernet(base64.urlsafe_b64encode(digest))


def encrypt_sensitive_message(message: str, master_key: str) -> str:
    return _fernet(master_key).encrypt(message.encode("utf-8")).decode("ascii")


def decrypt_sensitive_message(ciphertext: str, master_key: str) -> str:
    try:
        return _fernet(master_key).decrypt(ciphertext.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, UnicodeDecodeError) as exc:
        raise SensitiveMessageError("Sensitive notification body could not be decrypted") from exc
