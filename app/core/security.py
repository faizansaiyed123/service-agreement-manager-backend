from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings

_password_hash = PasswordHash.recommended()
ALGORITHM = "HS256"


def hash_password(password: str) -> str:
    return _password_hash.hash(password)


def verify_password(password: str, hashed: str) -> bool:
    return _password_hash.verify(password, hashed)


def create_token(*, subject: UUID, company_id: UUID, token_type: str, lifetime: timedelta,
                 session_id: UUID | None = None) -> tuple[str, str]:
    now = datetime.now(UTC)
    token_id = str(uuid4())
    claims: dict[str, object] = {
        "sub": str(subject), "company_id": str(company_id), "typ": token_type,
        "jti": token_id, "iat": now, "exp": now + lifetime,
    }
    if session_id:
        claims["sid"] = str(session_id)
    token = jwt.encode(claims, get_settings().jwt_secret_key, algorithm=ALGORITHM)
    return token, token_id


def decode_token(token: str) -> dict[str, object]:
    return jwt.decode(token, get_settings().jwt_secret_key, algorithms=[ALGORITHM],
                      options={"require": ["sub", "company_id", "typ", "exp", "iat", "jti"]})
