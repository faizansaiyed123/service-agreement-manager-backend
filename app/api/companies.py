from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Company, User
from app.schemas import CompanyRead, CompanyUpdate

router = APIRouter(prefix="/companies", tags=["companies"])


@router.get("/current", response_model=CompanyRead)
def current_company(user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Company:
    company = db.get(Company, user.company_id)
    if company is None:
        raise DomainError(404, "company_not_found", "Company not found")
    return company


@router.patch("/current", response_model=CompanyRead)
def update_current_company(
    payload: CompanyUpdate,
    user: User = Depends(require_roles("owner", "admin")),
    db: Session = Depends(get_db),
) -> Company:
    data = payload.model_dump(exclude_unset=True)
    if not data:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    for key, value in data.items():
        if isinstance(value, str) and key != "legal_name" and not value.strip():
            raise DomainError(422, "invalid_field", f"{key} cannot be blank")
        if key == "currency" and value:
            data[key] = value.upper()
    company = db.get(Company, user.company_id)
    if company is None:
        raise DomainError(404, "company_not_found", "Company not found")
    for key, value in data.items():
        setattr(company, key, value.strip() if isinstance(value, str) and key != "currency" else value)
    db.commit()
    db.refresh(company)
    return company
