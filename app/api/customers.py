from uuid import UUID

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Contact, Customer, ServiceLocation, User, Company
from app.schemas import ContactCreate, ContactRead, CustomerCreate, CustomerRead, CustomerUpdate, ServiceLocationCreate, ServiceLocationRead

router = APIRouter(prefix="/customers", tags=["customers"])


def scoped_customer(db: Session, company_id: UUID, customer_id: UUID) -> Customer:
    customer = db.scalar(select(Customer).where(Customer.id == customer_id, Customer.company_id == company_id))
    if customer is None:
        raise DomainError(404, "customer_not_found", "Customer not found")
    return customer


@router.post("", response_model=CustomerRead, status_code=201)
def create_customer(payload: CustomerCreate, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Customer:
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    company.customer_sequence += 1
    customer = Customer(
        company_id=user.company_id, customer_number=f"C-{company.customer_sequence:06d}", name=payload.name,
        kind=payload.kind, email=str(payload.email).lower() if payload.email else None,
        phone=payload.phone, notes=payload.notes,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return customer


@router.get("", response_model=list[CustomerRead])
def list_customers(
    q: str | None = Query(default=None, max_length=100),
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Customer]:
    stmt = select(Customer).where(Customer.company_id == user.company_id)
    if status:
        stmt = stmt.where(Customer.status == status)
    if q:
        stmt = stmt.where(Customer.name.ilike(f"%{q}%"))
    return list(db.scalars(stmt.order_by(Customer.created_at.desc(), Customer.id).limit(limit).offset(offset)).all())


@router.get("/{customer_id}", response_model=CustomerRead)
def get_customer(customer_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Customer:
    return scoped_customer(db, user.company_id, customer_id)


@router.patch("/{customer_id}", response_model=CustomerRead)
def update_customer(
    customer_id: UUID, payload: CustomerUpdate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Customer:
    customer = scoped_customer(db, user.company_id, customer_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if key == "email" and value:
            value = str(value).lower()
        if isinstance(value, str) and not value.strip():
            raise DomainError(422, "invalid_field", f"{key} cannot be blank")
        setattr(customer, key, value)
    db.commit()
    db.refresh(customer)
    return customer


@router.delete("/{customer_id}", status_code=204)
def deactivate_customer(customer_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Response:
    customer = scoped_customer(db, user.company_id, customer_id)
    customer.status = "inactive"
    db.commit()
    return Response(status_code=204)


@router.post("/{customer_id}/contacts", response_model=ContactRead, status_code=201)
def add_contact(
    customer_id: UUID, payload: ContactCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> Contact:
    customer = scoped_customer(db, user.company_id, customer_id)
    contact = Contact(
        company_id=user.company_id, customer_id=customer.id, full_name=payload.full_name.strip(),
        email=str(payload.email).lower() if payload.email else None, phone=payload.phone,
        is_billing_contact=payload.is_billing_contact,
    )
    db.add(contact)
    db.commit()
    db.refresh(contact)
    return contact


@router.get("/{customer_id}/contacts", response_model=list[ContactRead])
def list_contacts(customer_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Contact]:
    customer = scoped_customer(db, user.company_id, customer_id)
    return list(db.scalars(select(Contact).where(Contact.company_id == user.company_id, Contact.customer_id == customer.id).order_by(Contact.created_at)).all())


@router.post("/{customer_id}/service-locations", response_model=ServiceLocationRead, status_code=201)
def add_service_location(
    customer_id: UUID, payload: ServiceLocationCreate,
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> ServiceLocation:
    customer = scoped_customer(db, user.company_id, customer_id)
    location = ServiceLocation(company_id=user.company_id, customer_id=customer.id, **payload.model_dump())
    location.country_code = location.country_code.upper()
    db.add(location)
    db.commit()
    db.refresh(location)
    return location


@router.get("/{customer_id}/service-locations", response_model=list[ServiceLocationRead])
def list_service_locations(customer_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[ServiceLocation]:
    customer = scoped_customer(db, user.company_id, customer_id)
    return list(db.scalars(select(ServiceLocation).where(ServiceLocation.company_id == user.company_id, ServiceLocation.customer_id == customer.id, ServiceLocation.is_active.is_(True)).order_by(ServiceLocation.created_at)).all())
