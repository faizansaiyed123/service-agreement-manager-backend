import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from urllib.parse import quote
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.auth_cookies import set_auth_cookies
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.rate_limit import enforce_rate_limit
from app.core.security import create_token, hash_password
from app.db.session import get_db
from app.models import (
    AuthSession, Company, CompanyBranch, NotificationOutbox, TeamInvitation,
    TechnicianBranchMembership, TechnicianSkill, User,
)
from app.schemas.common import AuthenticatedSession, TokenPair
from app.schemas.team import (
    TechnicianInvitationAccept, TechnicianInvitationCreate, TechnicianInvitationRead,
    TechnicianInvitePreview, TechnicianProfileRead, TechnicianProfileUpdate,
)


router = APIRouter(prefix="/team", tags=["team"])
OWNER_ROLES = ("owner", "admin")


def _hash_token(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _utc(value: datetime) -> datetime:
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def _token_pair(user: User, session_id: UUID) -> tuple[TokenPair, str, datetime]:
    settings = get_settings()
    access, _ = create_token(
        subject=user.id, company_id=user.company_id, token_type="access",
        lifetime=timedelta(minutes=settings.access_token_minutes), session_id=session_id,
    )
    refresh, jti = create_token(
        subject=user.id, company_id=user.company_id, token_type="refresh",
        lifetime=timedelta(days=settings.refresh_token_days), session_id=session_id,
    )
    return TokenPair(access_token=access, refresh_token=refresh, expires_in=settings.access_token_minutes * 60), jti, datetime.now(UTC) + timedelta(days=settings.refresh_token_days)


def _session_response(request: Request, response: Response, pair: TokenPair):
    if request.headers.get("origin"):
        set_auth_cookies(response, pair.access_token, pair.refresh_token)
        return AuthenticatedSession(expires_in=pair.expires_in)
    return pair


def _get_invitation(db: Session, raw_token: str, *, lock: bool = False) -> TeamInvitation:
    stmt = select(TeamInvitation).where(TeamInvitation.token_hash == _hash_token(raw_token))
    if lock:
        stmt = stmt.with_for_update()
    invitation = db.scalar(stmt)
    now = datetime.now(UTC)
    if invitation is None:
        raise DomainError(404, "invitation_unavailable", "This invitation is invalid or unavailable")
    if invitation.status != "pending":
        raise DomainError(410, "invitation_unavailable", "This invitation is no longer available")
    if _utc(invitation.expires_at) <= now:
        invitation.status = "expired"
        db.commit()
        raise DomainError(410, "invitation_expired", "This invitation has expired. Ask the company owner to send a new one.")
    return invitation


@router.get("/invitations", response_model=list[TechnicianInvitationRead])
def list_invitations(
    user: User = Depends(require_roles(*OWNER_ROLES)),
    db: Session = Depends(get_db),
) -> list[TeamInvitation]:
    return list(db.scalars(
        select(TeamInvitation)
        .where(TeamInvitation.company_id == user.company_id)
        .order_by(TeamInvitation.created_at.desc(), TeamInvitation.id)
        .limit(100)
    ).all())


@router.post("/invitations", response_model=TechnicianInvitationRead, status_code=201)
def invite_technician(
    payload: TechnicianInvitationCreate,
    request: Request,
    user: User = Depends(require_roles(*OWNER_ROLES)),
    db: Session = Depends(get_db),
) -> TeamInvitation:
    email = str(payload.email).strip().lower()
    enforce_rate_limit(request, scope="team-invite-ip", limit=30, window_seconds=3600)
    enforce_rate_limit(request, scope="team-invite-email", limit=5, window_seconds=3600, subject=email, by_ip=False)

    if db.scalar(select(User.id).where(User.email == email)) is not None:
        raise DomainError(409, "email_already_registered", "This email already has a staff account. Deactivate or manage the existing account instead.")
    company = db.scalar(select(Company).where(Company.id == user.company_id, Company.is_active.is_(True)))
    if company is None:
        raise DomainError(403, "company_inactive", "Company account is inactive")

    active_branch_ids = {str(item) for item in db.scalars(select(CompanyBranch.id).where(
        CompanyBranch.company_id == user.company_id,
        CompanyBranch.is_active.is_(True),
    )).all()}
    requested_branches = {str(item) for item in payload.branch_ids}
    if requested_branches:
        if not requested_branches.issubset(active_branch_ids):
            raise DomainError(422, "invalid_branch_selection", "Choose only active branches belonging to this company")
    else:
        # Default a new technician to the company's current active branches.
        requested_branches = active_branch_ids
    for old in db.scalars(select(TeamInvitation).where(
        TeamInvitation.company_id == user.company_id,
        TeamInvitation.email == email,
        TeamInvitation.status == "pending",
    ).with_for_update()).all():
        old.status = "revoked"

    raw = secrets.token_urlsafe(48)
    expires_at = datetime.now(UTC) + timedelta(minutes=get_settings().team_invitation_token_minutes)
    invitation = TeamInvitation(
        company_id=user.company_id, invited_by_user_id=user.id,
        email=email, full_name=payload.full_name,
        token_hash=_hash_token(raw), branch_ids=sorted(requested_branches),
        skills=payload.skills, status="pending", expires_at=expires_at,
    )
    db.add(invitation)
    db.flush()

    settings = get_settings()
    url = f"{settings.team_invitation_url.rstrip('/')}/{quote(raw, safe='')}"
    body = (
        f"Hello {invitation.full_name},\n\n"
        f"{company.name} invited you to join its Service Agreement Manager team as a technician.\n\n"
        f"Choose your own password and activate your account using this one-time link:\n{url}\n\n"
        f"The link expires at {_utc(expires_at).isoformat()}. If you were not expecting this invitation, ignore this message."
    )
    db.add(NotificationOutbox(
        company_id=user.company_id, created_by_user_id=user.id,
        event_type="team.technician_invited", channel="email", recipient_email=email,
        subject=f"Invitation to join {company.name}", body=body,
        payload={"invitation_id": str(invitation.id), "role": "technician"},
        idempotency_key=f"team-invitation:{invitation.id}",
        request_fingerprint=hashlib.sha256(f"{invitation.id}:{email}".encode()).hexdigest(),
        status="queued", scheduled_at=datetime.now(UTC), next_attempt_at=datetime.now(UTC),
        attempt_count=0, max_attempts=settings.notification_default_max_attempts,
    ))
    db.commit()
    db.refresh(invitation)
    return invitation


@router.get("/invitations/public/{raw_token}", response_model=TechnicianInvitePreview)
def preview_invitation(raw_token: str, request: Request, response: Response, db: Session = Depends(get_db)) -> TechnicianInvitePreview:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    enforce_rate_limit(request, scope="team-invite-preview-ip", limit=60, window_seconds=300)
    invitation = _get_invitation(db, raw_token)
    company = db.get(Company, invitation.company_id)
    if company is None or not company.is_active:
        raise DomainError(404, "invitation_unavailable", "This invitation is invalid or unavailable")
    return TechnicianInvitePreview(email=invitation.email, full_name=invitation.full_name, company_name=company.name, expires_at=_utc(invitation.expires_at))


@router.post("/invitations/public/{raw_token}/accept", status_code=201)
def accept_invitation(
    raw_token: str,
    payload: TechnicianInvitationAccept,
    request: Request,
    response: Response,
    db: Session = Depends(get_db),
) -> TokenPair | AuthenticatedSession:
    response.headers["Cache-Control"] = "no-store"
    response.headers["Referrer-Policy"] = "no-referrer"
    enforce_rate_limit(request, scope="team-invite-accept-ip", limit=20, window_seconds=900)
    invitation = _get_invitation(db, raw_token, lock=True)
    company = db.get(Company, invitation.company_id)
    if company is None or not company.is_active:
        raise DomainError(410, "invitation_unavailable", "This company invitation is no longer available")
    if db.scalar(select(User.id).where(User.email == invitation.email)) is not None:
        raise DomainError(409, "email_already_registered", "An account with this email already exists. Ask the company owner to manage the existing account.")

    active_branches = set(db.scalars(select(CompanyBranch.id).where(
        CompanyBranch.company_id == invitation.company_id,
        CompanyBranch.is_active.is_(True),
    )).all())
    invited_branches = {UUID(str(item)) for item in (invitation.branch_ids or [])}
    if not invited_branches or not invited_branches.issubset(active_branches):
        raise DomainError(409, "invitation_branches_changed", "The assigned branches changed or are no longer active. Ask the company owner to send a fresh invitation.")

    try:
        technician = User(
            company_id=invitation.company_id, email=invitation.email, full_name=invitation.full_name,
            password_hash=hash_password(payload.password), role="technician", email_verified=True, is_active=True,
            branch_scope_enabled=True,
        )
        db.add(technician)
        db.flush()
        for skill in invitation.skills or []:
            clean = " ".join(str(skill).split())
            if clean:
                db.add(TechnicianSkill(
                    company_id=invitation.company_id, user_id=technician.id,
                    skill_name=clean, normalized_skill=clean.casefold(),
                ))
        for raw_branch_id in invitation.branch_ids or []:
            branch_id = UUID(str(raw_branch_id))
            db.add(TechnicianBranchMembership(
                company_id=invitation.company_id, user_id=technician.id, branch_id=branch_id,
            ))
        invitation.status = "accepted"
        invitation.accepted_at = datetime.now(UTC)
        session_id = uuid4()
        pair, jti, expires_at = _token_pair(technician, session_id)
        db.add(AuthSession(id=session_id, user_id=technician.id, refresh_jti=jti, expires_at=expires_at))
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(409, "invitation_conflict", "This invitation could not be accepted. Ask the company owner to send a fresh invitation.") from None
    return _session_response(request, response, pair)


@router.delete("/invitations/{invitation_id}", status_code=204)
def revoke_invitation(
    invitation_id: UUID,
    response: Response,
    user: User = Depends(require_roles(*OWNER_ROLES)),
    db: Session = Depends(get_db),
) -> Response:
    invitation = db.scalar(select(TeamInvitation).where(
        TeamInvitation.id == invitation_id,
        TeamInvitation.company_id == user.company_id,
    ).with_for_update())
    if invitation is None:
        raise DomainError(404, "invitation_not_found", "Invitation not found")
    if invitation.status == "pending":
        invitation.status = "revoked"
        db.commit()
    response.status_code = 204
    return response


@router.get("/technicians", response_model=list[TechnicianProfileRead])
def technician_profiles(
    user: User = Depends(require_roles(*OWNER_ROLES)),
    db: Session = Depends(get_db),
) -> list[TechnicianProfileRead]:
    technicians = list(db.scalars(select(User).where(
        User.company_id == user.company_id, User.role == "technician",
    ).order_by(User.full_name, User.id).limit(500)).all())
    if not technicians:
        return []
    ids = [item.id for item in technicians]
    skills_by_user: dict[UUID, list[str]] = {item.id: [] for item in technicians}
    for record in db.scalars(select(TechnicianSkill).where(
        TechnicianSkill.company_id == user.company_id, TechnicianSkill.user_id.in_(ids),
    ).order_by(TechnicianSkill.normalized_skill)).all():
        skills_by_user[record.user_id].append(record.skill_name)
    memberships = db.execute(
        select(TechnicianBranchMembership.user_id, CompanyBranch.id, CompanyBranch.name)
        .join(CompanyBranch, CompanyBranch.id == TechnicianBranchMembership.branch_id)
        .where(TechnicianBranchMembership.company_id == user.company_id, TechnicianBranchMembership.user_id.in_(ids))
    ).all()
    branch_ids: dict[UUID, list[UUID]] = {item.id: [] for item in technicians}
    branch_names: dict[UUID, list[str]] = {item.id: [] for item in technicians}
    for uid, branch_id, branch_name in memberships:
        branch_ids[uid].append(branch_id)
        branch_names[uid].append(branch_name)
    return [
        TechnicianProfileRead(
            id=item.id, full_name=item.full_name, email=item.email, is_active=item.is_active,
            skills=skills_by_user[item.id], branch_ids=branch_ids[item.id], branch_names=branch_names[item.id],
        )
        for item in technicians
    ]


@router.patch("/technicians/{technician_id}", response_model=TechnicianProfileRead)
def update_technician_profile(
    technician_id: UUID,
    payload: TechnicianProfileUpdate,
    user: User = Depends(require_roles(*OWNER_ROLES)),
    db: Session = Depends(get_db),
) -> TechnicianProfileRead:
    technician = db.scalar(select(User).where(
        User.id == technician_id, User.company_id == user.company_id, User.role == "technician",
    ).with_for_update())
    if technician is None:
        raise DomainError(404, "technician_not_found", "Technician not found")
    selected = {str(item) for item in payload.branch_ids}
    valid_ids = {str(item) for item in db.scalars(select(CompanyBranch.id).where(
        CompanyBranch.company_id == user.company_id,
        CompanyBranch.id.in_([UUID(item) for item in selected]),
        CompanyBranch.is_active.is_(True),
    )).all()}
    if valid_ids != selected:
        raise DomainError(422, "invalid_branch_selection", "Choose at least one active branch belonging to this company")

    db.query(TechnicianBranchMembership).filter(
        TechnicianBranchMembership.company_id == user.company_id,
        TechnicianBranchMembership.user_id == technician.id,
    ).delete(synchronize_session=False)
    db.query(TechnicianSkill).filter(
        TechnicianSkill.company_id == user.company_id,
        TechnicianSkill.user_id == technician.id,
    ).delete(synchronize_session=False)
    for branch_id in selected:
        db.add(TechnicianBranchMembership(
            company_id=user.company_id, user_id=technician.id, branch_id=UUID(branch_id),
        ))
    for skill in payload.skills:
        clean = " ".join(skill.split())
        db.add(TechnicianSkill(
            company_id=user.company_id, user_id=technician.id,
            skill_name=clean, normalized_skill=clean.casefold(),
        ))
    technician.branch_scope_enabled = True
    db.commit()
    return next(profile for profile in technician_profiles(user, db) if profile.id == technician.id)
