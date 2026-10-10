from datetime import date
from uuid import UUID
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.branch_schemas import (
    BranchClosureCreate,
    BranchClosureRead,
    BranchCreate,
    BranchRead,
    BranchUpdate,
    BusinessHoursRead,
    BusinessHoursReplace,
)
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import BranchBusinessHours, BranchClosure, Company, CompanyBranch, User

router = APIRouter(prefix="/branches", tags=["branches"])
BRANCH_ADMIN = ("owner", "admin")
BRANCH_MANAGER = ("owner", "admin", "manager")


def get_branch(db: Session, company_id: UUID, branch_id: UUID, *, lock: bool = False) -> CompanyBranch:
    stmt = select(CompanyBranch).where(
        CompanyBranch.company_id == company_id,
        CompanyBranch.id == branch_id,
    )
    if lock:
        stmt = stmt.with_for_update()
    branch = db.scalar(stmt)
    if branch is None:
        raise DomainError(404, "branch_not_found", "Branch not found")
    return branch


def ensure_timezone(value: str) -> None:
    try:
        ZoneInfo(value)
    except (ValueError, ZoneInfoNotFoundError):
        raise DomainError(422, "invalid_timezone", "timezone must be a valid IANA time-zone name") from None


def branch_values(payload: BranchCreate | BranchUpdate) -> dict:
    return payload.model_dump(exclude_unset=True)


def duplicate_code(db: Session, company_id: UUID, code: str, excluding: UUID | None = None) -> bool:
    stmt = select(CompanyBranch.id).where(
        CompanyBranch.company_id == company_id,
        CompanyBranch.code == code,
    )
    if excluding is not None:
        stmt = stmt.where(CompanyBranch.id != excluding)
    return db.scalar(stmt) is not None


def promote_primary(db: Session, company_id: UUID, target: CompanyBranch) -> None:
    if not target.is_active:
        raise DomainError(422, "inactive_primary_branch", "An inactive branch cannot be the primary branch")
    # Serialize primary-branch changes on the parent company row.
    db.scalar(select(Company).where(Company.id == company_id).with_for_update())
    primaries = db.scalars(select(CompanyBranch).where(
        CompanyBranch.company_id == company_id,
        CompanyBranch.is_primary.is_(True),
    ).with_for_update()).all()
    for current in primaries:
        if current.id != target.id:
            current.is_primary = False
    target.is_primary = True


@router.post("", response_model=BranchRead, status_code=201)
def create_branch(
    payload: BranchCreate,
    user: User = Depends(require_roles(*BRANCH_ADMIN)),
    db: Session = Depends(get_db),
) -> CompanyBranch:
    values = branch_values(payload)
    ensure_timezone(values["timezone"])
    company = db.scalar(select(Company).where(
        Company.id == user.company_id
    ).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    if duplicate_code(db, user.company_id, values["code"]):
        raise DomainError(409, "branch_code_already_exists", "A branch with this code already exists")
    already_has_primary = db.scalar(select(CompanyBranch.id).where(
        CompanyBranch.company_id == user.company_id,
        CompanyBranch.is_primary.is_(True),
    )) is not None
    requested_primary = bool(values.pop("is_primary", False))
    values["is_primary"] = requested_primary or not already_has_primary
    branch = CompanyBranch(company_id=user.company_id, **values)
    db.add(branch)
    db.flush()
    # A new branch starts with all seven weekdays explicitly closed until its
    # manager saves opening hours in the branch's local time zone.
    db.add_all([
        BranchBusinessHours(
            branch_id=branch.id,
            day_of_week=day,
            is_closed=True,
            opens_at=None,
            closes_at=None,
        )
        for day in range(7)
    ])
    if branch.is_primary:
        promote_primary(db, user.company_id, branch)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(409, "branch_conflict", "The branch conflicts with an existing company branch") from None
    db.refresh(branch)
    return branch


@router.get("", response_model=list[BranchRead])
def list_branches(
    active: bool | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[CompanyBranch]:
    stmt = select(CompanyBranch).where(CompanyBranch.company_id == user.company_id)
    if active is not None:
        stmt = stmt.where(CompanyBranch.is_active.is_(active))
    return list(db.scalars(stmt.order_by(CompanyBranch.is_primary.desc(), CompanyBranch.name, CompanyBranch.id).limit(limit).offset(offset)).all())


@router.get("/{branch_id}", response_model=BranchRead)
def read_branch(
    branch_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> CompanyBranch:
    return get_branch(db, user.company_id, branch_id)


@router.patch("/{branch_id}", response_model=BranchRead)
def update_branch(
    branch_id: UUID,
    payload: BranchUpdate,
    user: User = Depends(require_roles(*BRANCH_ADMIN)),
    db: Session = Depends(get_db),
) -> CompanyBranch:
    branch = get_branch(db, user.company_id, branch_id, lock=True)
    values = branch_values(payload)
    if not values:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    if values.get("timezone"):
        ensure_timezone(values["timezone"])
    if values.get("code") and duplicate_code(db, user.company_id, values["code"], excluding=branch.id):
        raise DomainError(409, "branch_code_already_exists", "A branch with this code already exists")
    requested_primary = values.pop("is_primary", None)
    active_value = values.get("is_active", branch.is_active)
    if requested_primary is True and not active_value:
        raise DomainError(422, "inactive_primary_branch", "An inactive branch cannot be the primary branch")
    for key, value in values.items():
        setattr(branch, key, value)
    if requested_primary is True:
        promote_primary(db, user.company_id, branch)
    elif requested_primary is False:
        branch.is_primary = False
    elif values.get("is_active") is False:
        branch.is_primary = False
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(409, "branch_conflict", "The branch update conflicts with another branch") from None
    db.refresh(branch)
    return branch


@router.get("/{branch_id}/business-hours", response_model=list[BusinessHoursRead])
def read_business_hours(
    branch_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BranchBusinessHours]:
    get_branch(db, user.company_id, branch_id)
    return list(db.scalars(select(BranchBusinessHours).where(
        BranchBusinessHours.branch_id == branch_id
    ).order_by(BranchBusinessHours.day_of_week)).all())


@router.put("/{branch_id}/business-hours", response_model=list[BusinessHoursRead])
def replace_business_hours(
    branch_id: UUID,
    payload: BusinessHoursReplace,
    user: User = Depends(require_roles(*BRANCH_MANAGER)),
    db: Session = Depends(get_db),
) -> list[BranchBusinessHours]:
    get_branch(db, user.company_id, branch_id, lock=True)
    current = db.scalars(select(BranchBusinessHours).where(
        BranchBusinessHours.branch_id == branch_id
    ).with_for_update()).all()
    for entry in current:
        db.delete(entry)
    db.flush()
    entries = [
        BranchBusinessHours(
            branch_id=branch_id,
            day_of_week=item.day_of_week,
            is_closed=item.is_closed,
            opens_at=item.opens_at,
            closes_at=item.closes_at,
        )
        for item in payload.hours
    ]
    db.add_all(entries)
    db.commit()
    return list(db.scalars(select(BranchBusinessHours).where(
        BranchBusinessHours.branch_id == branch_id
    ).order_by(BranchBusinessHours.day_of_week)).all())


@router.get("/{branch_id}/closures", response_model=list[BranchClosureRead])
def list_closures(
    branch_id: UUID,
    from_date: date | None = None,
    through_date: date | None = None,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[BranchClosure]:
    get_branch(db, user.company_id, branch_id)
    if from_date and through_date and through_date < from_date:
        raise DomainError(422, "invalid_date_range", "through_date must be on or after from_date")
    stmt = select(BranchClosure).where(BranchClosure.branch_id == branch_id)
    if from_date:
        stmt = stmt.where(BranchClosure.closure_date >= from_date)
    if through_date:
        stmt = stmt.where(BranchClosure.closure_date <= through_date)
    return list(db.scalars(stmt.order_by(BranchClosure.closure_date, BranchClosure.id).limit(limit).offset(offset)).all())


@router.post("/{branch_id}/closures", response_model=BranchClosureRead, status_code=201)
def create_closure(
    branch_id: UUID,
    payload: BranchClosureCreate,
    user: User = Depends(require_roles(*BRANCH_MANAGER)),
    db: Session = Depends(get_db),
) -> BranchClosure:
    get_branch(db, user.company_id, branch_id, lock=True)
    exists = db.scalar(select(BranchClosure.id).where(
        BranchClosure.branch_id == branch_id,
        BranchClosure.closure_date == payload.closure_date,
    ))
    if exists is not None:
        raise DomainError(409, "closure_already_exists", "A closure is already configured for this branch and date")
    closure = BranchClosure(
        branch_id=branch_id,
        closure_date=payload.closure_date,
        name=payload.name,
        description=payload.description,
    )
    db.add(closure)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise DomainError(409, "closure_already_exists", "A closure is already configured for this branch and date") from None
    db.refresh(closure)
    return closure


@router.delete("/{branch_id}/closures/{closure_id}", status_code=204)
def delete_closure(
    branch_id: UUID,
    closure_id: UUID,
    user: User = Depends(require_roles(*BRANCH_MANAGER)),
    db: Session = Depends(get_db),
) -> Response:
    get_branch(db, user.company_id, branch_id)
    closure = db.scalar(select(BranchClosure).where(
        BranchClosure.id == closure_id,
        BranchClosure.branch_id == branch_id,
    ))
    if closure is None:
        raise DomainError(404, "branch_closure_not_found", "Branch closure not found")
    db.delete(closure)
    db.commit()
    return Response(status_code=204)
