from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Integer, JSON, String, Text, UniqueConstraint, Uuid, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class WebhookEndpoint(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "webhook_endpoints"
    __table_args__ = (
        CheckConstraint("url like 'https://%'", name="https_webhook_url"),
        UniqueConstraint("company_id", "name", name="company_webhook_name"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    created_by_user_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("users.id", ondelete="RESTRICT"),
        nullable=False,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    url: Mapped[str] = mapped_column(String(2048), nullable=False)
    secret_ciphertext: Mapped[str] = mapped_column(Text, nullable=False)
    subscribed_events: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False, index=True)
    last_delivery_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_delivery_status: Mapped[str | None] = mapped_column(String(24))


class WebhookDelivery(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "webhook_deliveries"
    __table_args__ = (
        CheckConstraint(
            "status in ('queued','processing','sent','dead','cancelled')",
            name="valid_webhook_delivery_status",
        ),
        CheckConstraint("attempt_count >= 0 and max_attempts between 1 and 20", name="valid_webhook_attempt_limits"),
        UniqueConstraint("endpoint_id", "event_id", name="webhook_endpoint_event"),
    )

    company_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("companies.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    endpoint_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("webhook_endpoints.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    event_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), nullable=False)
    event_type: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    payload: Mapped[dict] = mapped_column(JSON, nullable=False)
    status: Mapped[str] = mapped_column(String(24), default="queued", nullable=False, index=True)
    scheduled_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    next_attempt_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), index=True, nullable=False)
    locked_until: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    attempt_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    max_attempts: Mapped[int] = mapped_column(Integer, default=8, nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    last_error: Mapped[str | None] = mapped_column(Text)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class WebhookDeliveryAttempt(Base, UUIDPrimaryKey):
    __tablename__ = "webhook_delivery_attempts"
    __table_args__ = (
        CheckConstraint("attempt_number > 0", name="positive_webhook_attempt_number"),
        CheckConstraint("status in ('started','sent','failed')", name="valid_webhook_attempt_status"),
        UniqueConstraint("delivery_id", "attempt_number", name="webhook_delivery_attempt_number"),
    )

    delivery_id: Mapped[UUID] = mapped_column(
        Uuid(as_uuid=True),
        ForeignKey("webhook_deliveries.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="started", nullable=False)
    http_status: Mapped[int | None] = mapped_column(Integer)
    response_body: Mapped[str | None] = mapped_column(Text)
    error_message: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
