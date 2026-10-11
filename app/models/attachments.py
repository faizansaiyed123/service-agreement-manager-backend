from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, CheckConstraint, DateTime, ForeignKey, String, Text, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class Attachment(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "attachments"
    __table_args__ = (
        CheckConstraint(
            "entity_type in ('customer','service_location','equipment','agreement','work_order','invoice')",
            name="valid_attachment_entity_type",
        ),
        CheckConstraint(
            "status in ('active','deleted')",
            name="valid_attachment_status",
        ),
        UniqueConstraint("company_id", "storage_key", name="company_attachment_storage_key"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    uploaded_by_user_id: Mapped[UUID | None] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="SET NULL"),
        index=True,
    )
    entity_type: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    entity_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False, index=True)
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(255), nullable=False)
    size_bytes: Mapped[int] = mapped_column(BigInteger, nullable=False)
    sha256: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(700), nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="active", nullable=False, index=True)
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    description: Mapped[str | None] = mapped_column(Text)
