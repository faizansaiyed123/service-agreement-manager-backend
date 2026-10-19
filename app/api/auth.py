from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import jwt
from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.config import get_settings
from app.core.auth_cookies import REFRESH_COOKIE, clear_auth_cookies, set_auth_cookies
from app.core.errors import DomainError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_token, decode_token, hash_password, verify_password
from app.db.session import get_db
from app.models import AuthSession, Company, User
from app.schemas import AuthenticatedSession, LoginRequest, RefreshRequest, RegisterRequest, TokenPair, UserRead
from app.user_schemas import PasswordChange

router = APIRouter(prefix="/auth", tags=["authentication"])


def token_pair(user: User, session_id: UUID) -> tuple[TokenPair, str, datetime]:
    settings = get_settings()
    access, _ = create_token(
        subject=user.id, company_id=user.company_id, token_type="access",
        lifetime=timedelta(minutes=settings.access_token_minutes), session_id=session_id,
    )
    expires_at = datetime.now(UTC) + timedelta(days=settings.refresh_token_days)
    refresh, jti = create_token(
        subject=user.id, company_id=user.company_id, token_type="refresh",
        lifetime=timedelta(days=settings.refresh_token_days), session_id=session_id,
    )
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60), jti, expires_at


def browser_or_api_session(
    request: Request,
    response: Response,
    pair: TokenPair,
) -> TokenPair | AuthenticatedSession:
    # Browser requests always carry Origin. Never return bearer tokens to JavaScript.
    # Non-browser API clients without Origin retain the explicit bearer-token flow.
    if request.headers.get("origin"):
        set_auth_cookies(response, pair.access_token, pair.refresh_token)
        return AuthenticatedSession(expires_in=pair.expires_in)
    return pair


@router.post("/register", response_model=TokenPair | AuthenticatedSession, status_code=201)
def register(payload: RegisterRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair | AuthenticatedSession:
    email = str(payload.email).lower()
    enforce_rate_limit(request, scope="register-ip", limit=10, window_seconds=3600)
    enforce_rate_limit(request, scope="register-email", limit=3, window_seconds=3600, subject=email, by_ip=False)
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise DomainError(409, "email_already_registered", "An account with this email already exists")
    company = Company(name=payload.company_name.strip())
    db.add(company)
    db.flush()
    user = User(company_id=company.id, email=email, full_name=payload.full_name.strip(),
                password_hash=hash_password(payload.password), role="owner")
    db.add(user)
    db.flush()
    session_id = uuid4()
    pair, jti, expires_at = token_pair(user, session_id)
    db.add(AuthSession(id=session_id, user_id=user.id, refresh_jti=jti, expires_at=expires_at))
    db.commit()
    return browser_or_api_session(request, response, pair)


@router.post("/login", response_model=TokenPair | AuthenticatedSession)
def login(payload: LoginRequest, request: Request, response: Response, db: Session = Depends(get_db)) -> TokenPair | AuthenticatedSession:
    email = str(payload.email).lower()
    enforce_rate_limit(request, scope="login-ip", limit=30, window_seconds=60)
    enforce_rate_limit(request, scope="login-email", limit=10, window_seconds=900, subject=email, by_ip=False)
    user = db.scalar(select(User).where(User.email == email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise DomainError(401, "invalid_credentials", "Email or password is incorrect")
    if not user.is_active:
        raise DomainError(403, "user_inactive", "This user account is inactive")
    company = db.get(Company, user.company_id)
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "This company account is inactive")
    session_id = uuid4()
    pair, jti, expires_at = token_pair(user, session_id)
    db.add(AuthSession(id=session_id, user_id=user.id, refresh_jti=jti, expires_at=expires_at))
    db.commit()
    return browser_or_api_session(request, response, pair)


@router.post("/refresh", response_model=TokenPair | AuthenticatedSession)
def refresh(
    request: Request,
    response: Response,
    payload: RefreshRequest | None = None,
    db: Session = Depends(get_db),
) -> TokenPair | AuthenticatedSession:
    raw_refresh_token = request.cookies.get(REFRESH_COOKIE)
    if request.headers.get("origin") and not raw_refresh_token:
        raise DomainError(401, "cookie_session_required", "Browser sessions must use the refresh cookie")
    if not raw_refresh_token and payload is not None:
        raw_refresh_token = payload.refresh_token
    if not raw_refresh_token:
        raise DomainError(401, "invalid_refresh_token", "The refresh token is invalid or expired")
    try:
        claims = decode_token(raw_refresh_token)
        if claims.get("typ") != "refresh":
            raise ValueError("wrong token type")
        user_id, company_id = UUID(str(claims["sub"])), UUID(str(claims["company_id"]))
        session_id, jti = UUID(str(claims["sid"])), str(claims["jti"])
    except (jwt.PyJWTError, ValueError, KeyError, TypeError):
        raise DomainError(401, "invalid_refresh_token", "The refresh token is invalid or expired") from None
    session = db.scalar(select(AuthSession).where(AuthSession.id == session_id).with_for_update())
    now = datetime.now(UTC)
    if session is None or session.revoked_at is not None or session.refresh_jti != jti:
        raise DomainError(401, "refresh_token_reused", "The refresh session is invalid or has been rotated")
    expiry = session.expires_at
    if expiry.tzinfo is None:
        expiry = expiry.replace(tzinfo=UTC)
    if expiry <= now:
        session.revoked_at = now
        db.commit()
        raise DomainError(401, "refresh_token_expired", "The refresh session has expired")
    user = db.get(User, user_id)
    if user is None or user.company_id != company_id or not user.is_active:
        session.revoked_at = now
        db.commit()
        raise DomainError(401, "invalid_session", "The user session is no longer valid")
    pair, next_jti, next_expiry = token_pair(user, session_id)
    session.refresh_jti, session.expires_at = next_jti, next_expiry
    db.commit()
    return browser_or_api_session(request, response, pair)


@router.post("/change-password", status_code=204)
def change_password(
    payload: PasswordChange,
    response: Response,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    if not verify_password(payload.current_password, user.password_hash):
        raise DomainError(401, "invalid_current_password", "Current password is incorrect")
    if verify_password(payload.new_password, user.password_hash):
        raise DomainError(409, "password_unchanged", "New password must differ from current password")
    user.password_hash = hash_password(payload.new_password)
    now = datetime.now(UTC)
    sessions = db.scalars(select(AuthSession).where(
        AuthSession.user_id == user.id,
        AuthSession.revoked_at.is_(None),
    ).with_for_update()).all()
    for session in sessions:
        session.revoked_at = now
    db.commit()
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.post("/logout", status_code=204)
def logout(response: Response, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    sessions = db.scalars(select(AuthSession).where(AuthSession.user_id == user.id, AuthSession.revoked_at.is_(None))).all()
    now = datetime.now(UTC)
    for session in sessions:
        session.revoked_at = now
    db.commit()
    clear_auth_cookies(response)
    response.status_code = 204
    return response


@router.get("/me", response_model=UserRead)
def me(user: User = Depends(get_current_user)) -> User:
    return user
