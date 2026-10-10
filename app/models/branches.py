from datetime import date, time
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, Date, ForeignKey, Index, String, Text, Time, UniqueConstraint, Uuid, text
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class CompanyBranch(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "company_branches"
    __table_args__ = (
        UniqueConstraint("company_id", "code", name="company_branch_code"),
        CheckConstraint("length(code) > 0", name="nonempty_code"),
        Index(
            "uq_company_branches_single_primary",
            "company_id",
            unique=True,
            postgresql_where=text("is_primary"),
            sqlite_where=text("is_primary"),
        ),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False)
    timezone: Mapped[str] = mapped_column(String(64), default="UTC", nullable=False)
    address_line1: Mapped[str | None] = mapped_column(String(180))
    address_line2: Mapped[str | None] = mapped_column(String(180))
    city: Mapped[str | None] = mapped_column(String(100))
    region: Mapped[str | None] = mapped_column(String(100))
    postal_code: Mapped[str | None] = mapped_column(String(24))
    country_code: Mapped[str] = mapped_column(String(2), default="US", nullable=False)
    phone: Mapped[str | None] = mapped_column(String(40))
    email: Mapped[str | None] = mapped_column(String(320))
    is_primary: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)


class BranchBusinessHours(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "branch_business_hours"
    __table_args__ = (
        CheckConstraint("day_of_week between 0 and 6", name="valid_day_of_week"),
        CheckConstraint(
            "((is_closed = true and opens_at is null and closes_at is null) or "
            "(is_closed = false and opens_at is not null and closes_at is not null and closes_at > opens_at))",
            name="valid_hours_window",
        ),
        UniqueConstraint("branch_id", "day_of_week", name="branch_business_hours_day"),
    )

    branch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    day_of_week: Mapped[int] = mapped_column(nullable=False)
    is_closed: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    opens_at: Mapped[time | None] = mapped_column(Time())
    closes_at: Mapped[time | None] = mapped_column(Time())


class BranchClosure(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "branch_closures"
    __table_args__ = (
        CheckConstraint("length(name) > 0", name="nonempty_name"),
        UniqueConstraint("branch_id", "closure_date", name="branch_closure_date"),
    )

    branch_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"),
        index=True, nullable=False,
    )
    closure_date: Mapped[date] = mapped_column(Date(), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(160), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
