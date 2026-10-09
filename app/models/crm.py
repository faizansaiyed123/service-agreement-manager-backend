from uuid import UUID

from sqlalchemy import Boolean, ForeignKey, String, Text, Uuid, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Timestamped, UUIDPrimaryKey


class Customer(UUIDPrimaryKey, Timestamped):
    __tablename__ = "customers"
    __table_args__ = (UniqueConstraint("company_id", "customer_number", name="customer_company_number"),)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_number: Mapped[str] = mapped_column(String(32), nullable=False)
    kind: Mapped[str] = mapped_column(String(24), default="residential", nullable=False)
    name: Mapped[str] = mapped_column(String(180), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    status: Mapped[str] = mapped_column(String(20), default="active", nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    contacts: Mapped[list["Contact"]] = relationship(back_populates="customer", cascade="all, delete-orphan")
    service_locations: Mapped[list["ServiceLocation"]] = relationship(back_populates="customer", cascade="all, delete-orphan")


class Contact(UUIDPrimaryKey, Timestamped):
    __tablename__ = "contacts"
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    email: Mapped[str | None] = mapped_column(String(320))
    phone: Mapped[str | None] = mapped_column(String(40))
    is_billing_contact: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    customer: Mapped[Customer] = relationship(back_populates="contacts")


class ServiceLocation(UUIDPrimaryKey, Timestamped):
    __tablename__ = "service_locations"
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    address_line1: Mapped[str] = mapped_column(String(180), nullable=False)
    address_line2: Mapped[str | None] = mapped_column(String(180))
    city: Mapped[str] = mapped_column(String(100), nullable=False)
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(24))
    country_code: Mapped[str] = mapped_column(String(2), default="US", nullable=False)
    access_instructions: Mapped[str | None] = mapped_column(Text)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    customer: Mapped[Customer] = relationship(back_populates="service_locations")
