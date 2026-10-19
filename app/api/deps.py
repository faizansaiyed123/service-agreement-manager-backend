from datetime import UTC, datetime
from uuid import UUID

import jwt
from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.auth_cookies import ACCESS_COOKIE
from app.core.errors import DomainError
from app.core.security import decode_token
from app.db.session import get_db
from app.models import AuthSession, Company, User

bearer = HTTPBearer(auto_error=False)


def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    db: Session = Depends(get_db),
) -> User:
    cookie_token = request.cookies.get(ACCESS_COOKIE)
    browser_request = bool(request.headers.get("origin") or request.headers.get("sec-fetch-site"))
    if browser_request:
        # Do not accept bearer tokens from browsers: older localStorage sessions must not
        # remain a way to authenticate after the HttpOnly-cookie migration.
        token = cookie_token
    else:
        token = credentials.credentials if credentials is not None else cookie_token
    if not token:
        raise DomainError(401, "authentication_required", "A valid session cookie or API bearer token is required")
    try:
        claims = decode_token(token)
        if claims.get("typ") != "access":
            raise ValueError("wrong token type")
        user_id = UUID(str(claims["sub"]))
        company_id = UUID(str(claims["company_id"]))
        session_id = UUID(str(claims["sid"]))
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise DomainError(401, "invalid_token", "The access token is invalid or expired") from None
    session = db.get(AuthSession, session_id)
    if session is None or session.user_id != user_id or session.revoked_at is not None:
        raise DomainError(401, "invalid_session", "The user session is no longer valid")
    session_expiry = session.expires_at
    if session_expiry.tzinfo is None:
        session_expiry = session_expiry.replace(tzinfo=UTC)
    if session_expiry <= datetime.now(UTC):
        raise DomainError(401, "invalid_session", "The user session has expired")
    user = db.get(User, user_id)
    if user is None or not user.is_active or user.company_id != company_id:
        raise DomainError(401, "invalid_session", "The user session is no longer valid")
    company = db.get(Company, company_id)
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    return user


def require_roles(*roles: str):
    def dependency(user: User = Depends(get_current_user)) -> User:
        if user.role not in roles:
            raise DomainError(403, "insufficient_permissions", "You do not have permission for this action")
        return user
    return dependency
