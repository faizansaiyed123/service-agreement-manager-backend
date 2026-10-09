from datetime import date
from decimal import Decimal
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, ForeignKey, Integer, Numeric, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class Equipment(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "equipment"
    __table_args__ = (
        CheckConstraint("status in ('active','inactive','decommissioned')", name="valid_equipment_status"),
        UniqueConstraint("company_id", "asset_number", name="company_asset_number"),
    )
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False)
    service_location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("service_locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    asset_number: Mapped[str] = mapped_column(String(32), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    manufacturer: Mapped[str | None] = mapped_column(String(120))
    model_number: Mapped[str | None] = mapped_column(String(120))
    serial_number: Mapped[str | None] = mapped_column(String(120))
    installed_on: Mapped[date | None] = mapped_column(Date())
    warranty_expires_on: Mapped[date | None] = mapped_column(Date())
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)


class ServiceCatalogItem(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "service_catalog_items"
    __table_args__ = (
        CheckConstraint("unit_price >= 0", name="nonnegative_unit_price"),
        CheckConstraint("duration_minutes >= 0", name="nonnegative_duration"),
        UniqueConstraint("company_id", "service_code", name="company_service_code"),
    )
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    service_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str] = mapped_column(String(60), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), default=Decimal("0.00"), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True, nullable=False)
