from datetime import date, datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, ForeignKey, JSON, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class RecurringInvoiceSchedule(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "recurring_invoice_schedules"
    __table_args__ = (
        CheckConstraint(
            "frequency in ('monthly','quarterly','semi_annual','annual')",
            name="valid_recurring_invoice_frequency",
        ),
        CheckConstraint("due_days between 0 and 365", name="valid_recurring_invoice_due_days"),
        UniqueConstraint("company_id", "name", name="company_recurring_invoice_name"),
    )

    company_id: Mapped[UUID] = mapped_column(
        ForeignKey("companies.id", ondelete="CASCADE"), nullable=False, index=True
    )
    customer_id: Mapped[UUID] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    service_location_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("service_locations.id", ondelete="RESTRICT")
    )
    agreement_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("agreements.id", ondelete="RESTRICT")
    )
    created_by_user_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL")
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    frequency: Mapped[str] = mapped_column(String(24), nullable=False)
    next_invoice_date: Mapped[date] = mapped_column(Date(), nullable=False, index=True)
    due_days: Mapped[int] = mapped_column(default=30, nullable=False)
    currency: Mapped[str] = mapped_column(String(3), nullable=False)
    discount_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    tax_percent: Mapped[Decimal] = mapped_column(Numeric(5, 2), default=Decimal("0"), nullable=False)
    notes: Mapped[str | None] = mapped_column(Text)
    line_templates: Mapped[list] = mapped_column(JSON, nullable=False)
    auto_issue: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_invoice_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("invoices.id", ondelete="SET NULL")
    )
    last_run_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_run_error: Mapped[str | None] = mapped_column(Text)
