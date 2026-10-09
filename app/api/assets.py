from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.assets_schemas import (
    EquipmentCreate, EquipmentRead, EquipmentUpdate, ServiceCatalogCreate,
    ServiceCatalogRead, ServiceCatalogUpdate,
)
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Customer, Equipment, ServiceCatalogItem, ServiceLocation, User

equipment_router = APIRouter(prefix="/equipment", tags=["equipment"])
catalog_router = APIRouter(prefix="/service-catalog", tags=["service catalog"])


def scoped_equipment(db: Session, company_id: UUID, equipment_id: UUID) -> Equipment:
    item = db.scalar(select(Equipment).where(Equipment.id == equipment_id, Equipment.company_id == company_id))
    if item is None:
        raise DomainError(404, "equipment_not_found", "Equipment not found")
    return item


def scoped_catalog_item(db: Session, company_id: UUID, item_id: UUID) -> ServiceCatalogItem:
    item = db.scalar(select(ServiceCatalogItem).where(
        ServiceCatalogItem.id == item_id, ServiceCatalogItem.company_id == company_id,
    ))
    if item is None:
        raise DomainError(404, "catalog_item_not_found", "Service catalog item not found")
    return item


@equipment_router.post("", response_model=EquipmentRead, status_code=201)
def create_equipment(
    payload: EquipmentCreate, user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> Equipment:
    customer = db.scalar(select(Customer).where(
        Customer.id == payload.customer_id, Customer.company_id == user.company_id,
    ))
    location = db.scalar(select(ServiceLocation).where(
        ServiceLocation.id == payload.service_location_id,
        ServiceLocation.company_id == user.company_id,
        ServiceLocation.customer_id == payload.customer_id,
        ServiceLocation.is_active.is_(True),
    ))
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    if location is None:
        raise DomainError(404, "service_location_not_found", "Service location not found for this customer")
    item = Equipment(
        company_id=user.company_id, customer_id=customer.id, service_location_id=location.id,
        asset_number=f"EQ-{uuid4().hex[:10].upper()}", **payload.model_dump(exclude={"customer_id", "service_location_id"}),
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@equipment_router.get("", response_model=list[EquipmentRead])
def list_equipment(
    customer_id: UUID | None = None,
    status: str | None = Query(default=None, pattern="^(active|inactive|decommissioned)$"),
    q: str | None = Query(default=None, max_length=100),
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[Equipment]:
    stmt = select(Equipment).where(Equipment.company_id == user.company_id)
    if customer_id:
        stmt = stmt.where(Equipment.customer_id == customer_id)
    if status:
        stmt = stmt.where(Equipment.status == status)
    if q:
        term = f"%{q}%"
        stmt = stmt.where(
            Equipment.category.ilike(term) | Equipment.manufacturer.ilike(term)
            | Equipment.model_number.ilike(term) | Equipment.serial_number.ilike(term)
        )
    return list(db.scalars(stmt.order_by(Equipment.created_at.desc()).limit(limit).offset(offset)).all())


@equipment_router.get("/{equipment_id}", response_model=EquipmentRead)
def get_equipment(equipment_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> Equipment:
    return scoped_equipment(db, user.company_id, equipment_id)


@equipment_router.patch("/{equipment_id}", response_model=EquipmentRead)
def update_equipment(
    equipment_id: UUID, payload: EquipmentUpdate,
    user: User = Depends(require_roles("owner", "admin", "manager", "staff")),
    db: Session = Depends(get_db),
) -> Equipment:
    item = scoped_equipment(db, user.company_id, equipment_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str) and key == "category" and not value.strip():
            raise DomainError(422, "invalid_field", "category cannot be blank")
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item


@catalog_router.post("", response_model=ServiceCatalogRead, status_code=201)
def create_catalog_item(
    payload: ServiceCatalogCreate,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> ServiceCatalogItem:
    code = payload.service_code.upper()
    existing = db.scalar(select(ServiceCatalogItem.id).where(
        ServiceCatalogItem.company_id == user.company_id, ServiceCatalogItem.service_code == code,
    ))
    if existing:
        raise DomainError(409, "service_code_exists", "A service with this code already exists")
    item = ServiceCatalogItem(company_id=user.company_id, service_code=code, **payload.model_dump(exclude={"service_code"}))
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@catalog_router.get("", response_model=list[ServiceCatalogRead])
def list_catalog(
    q: str | None = Query(default=None, max_length=100),
    include_inactive: bool = False,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user), db: Session = Depends(get_db),
) -> list[ServiceCatalogItem]:
    stmt = select(ServiceCatalogItem).where(ServiceCatalogItem.company_id == user.company_id)
    if not include_inactive:
        stmt = stmt.where(ServiceCatalogItem.is_active.is_(True))
    if q:
        term = f"%{q}%"
        stmt = stmt.where(ServiceCatalogItem.name.ilike(term) | ServiceCatalogItem.service_code.ilike(term))
    return list(db.scalars(stmt.order_by(ServiceCatalogItem.name).limit(limit).offset(offset)).all())


@catalog_router.get("/{item_id}", response_model=ServiceCatalogRead)
def get_catalog_item(item_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> ServiceCatalogItem:
    return scoped_catalog_item(db, user.company_id, item_id)


@catalog_router.patch("/{item_id}", response_model=ServiceCatalogRead)
def update_catalog_item(
    item_id: UUID, payload: ServiceCatalogUpdate,
    user: User = Depends(require_roles("owner", "admin", "manager")),
    db: Session = Depends(get_db),
) -> ServiceCatalogItem:
    item = scoped_catalog_item(db, user.company_id, item_id)
    for key, value in payload.model_dump(exclude_unset=True).items():
        if isinstance(value, str) and key in {"name", "category"} and not value.strip():
            raise DomainError(422, "invalid_field", f"{key} cannot be blank")
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return item
