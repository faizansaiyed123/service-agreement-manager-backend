from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.errors import DomainError
from app.core.security import hash_password
from app.db.session import get_db
from app.models import AuthSession, User
from app.schemas import UserRead
from app.user_schemas import PasswordReset, UserCreate, UserUpdate

router = APIRouter(prefix="/users", tags=["users"])


def scoped_user(db: Session, company_id: UUID, user_id: UUID) -> User:
    user = db.scalar(select(User).where(User.id == user_id, User.company_id == company_id))
    if user is None:
        raise DomainError(404, "user_not_found", "User not found")
    return user


@router.post("", response_model=UserRead, status_code=201)
def create_user(payload: UserCreate, actor: User = Depends(require_roles("owner", "admin")), db: Session = Depends(get_db)) -> User:
    role = payload.role
    if actor.role != "owner" and role in {"owner", "admin"}:
        raise DomainError(403, "role_assignment_forbidden", "Only an owner can create owners or administrators")
    email = str(payload.email).lower()
    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise DomainError(409, "email_already_registered", "An account with this email already exists")
    user = User(
        company_id=actor.company_id, email=email, full_name=payload.full_name.strip(),
        password_hash=hash_password(payload.password), role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("", response_model=list[UserRead])
def list_users(
    role: str | None = Query(default=None, pattern="^(owner|admin|manager|technician|billing|staff)$"),
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    actor: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> list[User]:
    stmt = select(User).where(User.company_id == actor.company_id)
    if role:
        stmt = stmt.where(User.role == role)
    if active is not None:
        stmt = stmt.where(User.is_active.is_(active))
    return list(db.scalars(stmt.order_by(User.created_at, User.id).limit(limit).offset(offset)).all())


@router.get("/{user_id}", response_model=UserRead)
def get_user(user_id: UUID, actor: User = Depends(require_roles("owner", "admin", "manager")), db: Session = Depends(get_db)) -> User:
    return scoped_user(db, actor.company_id, user_id)


@router.patch("/{user_id}", response_model=UserRead)
def update_user(
    user_id: UUID, payload: UserUpdate,
    actor: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> User:
    target = scoped_user(db, actor.company_id, user_id)
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    if target.id == actor.id and (
        updates.get("is_active") is False or updates.get("role") not in (None, actor.role)
    ):
        raise DomainError(409, "self_lockout_prevented", "You cannot deactivate yourself or change your own role")
    requested_role = updates.get("role")
    if actor.role != "owner" and (target.role in {"owner", "admin"} or requested_role in {"owner", "admin"}):
        raise DomainError(403, "role_assignment_forbidden", "Only an owner can manage owner/admin accounts")
    for key, value in updates.items():
        if key == "full_name":
            value = value.strip()
            if not value:
                raise DomainError(422, "invalid_field", "full_name cannot be blank")
        setattr(target, key, value)
    db.commit()
    db.refresh(target)
    return target


@router.post("/{user_id}/reset-password", response_model=UserRead)
def reset_password(
    user_id: UUID, payload: PasswordReset,
    actor: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> User:
    target = scoped_user(db, actor.company_id, user_id)
    if actor.role != "owner" and target.role in {"owner", "admin"}:
        raise DomainError(403, "role_assignment_forbidden", "Only an owner can reset an owner/admin password")
    target.password_hash = hash_password(payload.new_password)
    for session in db.scalars(select(AuthSession).where(
        AuthSession.user_id == target.id, AuthSession.revoked_at.is_(None)
    )).all():
        session.revoked_at = datetime.now(UTC)
    db.commit()
    db.refresh(target)
    return target
