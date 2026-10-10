from datetime import date, datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class AgreementRenewal(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "agreement_renewals"
    __table_args__ = (
        CheckConstraint("status in ('offered','accepted','declined','expired','cancelled')", name="valid_status"),
        CheckConstraint("proposed_end_date >= proposed_start_date", name="end_after_start"),
        UniqueConstraint("renewed_agreement_id", name="unique_successor_agreement"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False
    )
    source_agreement_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="RESTRICT"), index=True, nullable=False
    )
    renewed_agreement_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("agreements.id", ondelete="RESTRICT")
    )
    offered_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL")
    )
    status: Mapped[str] = mapped_column(String(24), default="offered", nullable=False, index=True)
    proposed_start_date: Mapped[date] = mapped_column(Date(), nullable=False)
    proposed_end_date: Mapped[date] = mapped_column(Date(), nullable=False)
    expires_on: Mapped[date] = mapped_column(Date(), nullable=False)
    snapshot: Mapped[dict] = mapped_column(JSON, nullable=False)
    accepted_by_name: Mapped[str | None] = mapped_column(String(160))
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    acceptance_method: Mapped[str | None] = mapped_column(String(24))
    acceptance_reference: Mapped[str | None] = mapped_column(String(255))
    decline_reason: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False
    )
