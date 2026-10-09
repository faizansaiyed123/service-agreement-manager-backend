from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, Integer, JSON, Numeric, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class Agreement(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "agreements"
    __table_args__ = (
        CheckConstraint("status in ('draft','proposed','accepted','active','suspended','cancelled','expired')", name="valid_status"),
        CheckConstraint("billing_frequency in ('monthly','quarterly','semi_annual','annual','one_time')", name="valid_billing_frequency"),
        CheckConstraint("total_amount >= 0", name="nonnegative_total"),
        CheckConstraint("renewal_notice_days >= 0", name="nonnegative_notice_days"),
        CheckConstraint("end_date >= start_date", name="end_after_start"),
        UniqueConstraint("company_id", "agreement_number", name="company_agreement_number"),
    )
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="RESTRICT"), index=True, nullable=False)
    service_location_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("service_locations.id", ondelete="RESTRICT"), index=True, nullable=False)
    agreement_number: Mapped[str] = mapped_column(String(32), nullable=False)
    title: Mapped[str] = mapped_column(String(180), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="draft", nullable=False, index=True)
    start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    billing_frequency: Mapped[str] = mapped_column(String(24), default="annual", nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    auto_renew: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    renewal_notice_days: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    terms_text: Mapped[str] = mapped_column(Text, default="", nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), default=Decimal("0.00"), nullable=False)
    accepted_by_name: Mapped[str | None] = mapped_column(String(160))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acceptance_method: Mapped[str | None] = mapped_column(String(24))
    acceptance_reference: Mapped[str | None] = mapped_column(String(255))
    cancelled_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    cancellation_reason: Mapped[str | None] = mapped_column(Text)
    version_number: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    lines: Mapped[list["AgreementLine"]] = relationship(back_populates="agreement", cascade="all, delete-orphan", order_by="AgreementLine.created_at")


class AgreementLine(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "agreement_lines"
    __table_args__ = (
        CheckConstraint("quantity > 0", name="positive_quantity"),
        CheckConstraint("unit_price >= 0", name="nonnegative_price"),
        CheckConstraint("line_total >= 0", name="nonnegative_line_total"),
    )
    agreement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), index=True, nullable=False)
    catalog_item_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("service_catalog_items.id", ondelete="SET NULL"))
    service_code: Mapped[str] = mapped_column(String(32), nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    unit_price: Mapped[Decimal] = mapped_column(Numeric(12, 2), nullable=False)
    line_total: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    agreement: Mapped[Agreement] = relationship(back_populates="lines")


class AgreementVersion(Base, UUIDPrimaryKey):
    __tablename__ = "agreement_versions"
    __table_args__ = (
        UniqueConstraint("agreement_id", "version_number", name="agreement_version_number"),
        CheckConstraint("version_number > 0", name="positive_version_number"),
    )
    agreement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), index=True, nullable=False)
    version_number: Mapped[int] = mapped_column(Integer, nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    change_reason: Mapped[str] = mapped_column(String(200), nullable=False)
    created_by: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)


class AgreementEvent(Base, UUIDPrimaryKey):
    __tablename__ = "agreement_events"
    agreement_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="CASCADE"), index=True, nullable=False)
    actor_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))
    event_type: Mapped[str] = mapped_column(String(60), nullable=False)
    from_status: Mapped[str | None] = mapped_column(String(24))
    to_status: Mapped[str | None] = mapped_column(String(24))
    detail: Mapped[dict | None] = mapped_column(JSON)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
