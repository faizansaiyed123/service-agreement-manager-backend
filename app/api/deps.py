from uuid import UUID

import jwt
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import Company, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    if credentials is None:
        raise DomainError(401, "authentication_required", "A bearer access token is required")
    try:
        claims = decode_token(credentials.credentials)
        if claims.get("typ") != "access":
            raise ValueError("wrong token type")
        user_id = UUID(str(claims["sub"]))
        company_id = UUID(str(claims["company_id"]))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise DomainError(401, "invalid_token", "The access token is invalid or expired") from None
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.company_id != company_id:
        raise DomainError(401, "invalid_session", "The user session is no longer valid")
    company = db.get(Company, company_id)
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "This company account is inactive")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise DomainError(403, "insufficient_permissions", "You do not have permission for this action")
        return user
    return dependency
