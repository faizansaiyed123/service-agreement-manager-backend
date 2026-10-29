from datetime import datetime
from uuid import UUID

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, Uuid, true
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class CustomerPortalIdentity(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "customer_portal_identities"
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False, index=True)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)


class CustomerPortalSession(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "customer_portal_sessions"
    portal_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customer_portal_identities.id", ondelete="CASCADE"), index=True, nullable=False)
    refresh_jti: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class CustomerPortalMembership(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "customer_portal_memberships"
    __table_args__ = (UniqueConstraint("portal_user_id", "company_id", "customer_id", name="customer_portal_membership_unique"),)
    portal_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customer_portal_identities.id", ondelete="CASCADE"), index=True, nullable=False)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, server_default=true(), nullable=False)
    invited_by_user_id: Mapped[UUID | None] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="SET NULL"))


class CustomerPortalInvitation(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "customer_portal_invitations"
    __table_args__ = (CheckConstraint("status in ('pending','accepted','revoked','expired')", name="valid_status"),)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    customer_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("customers.id", ondelete="CASCADE"), index=True, nullable=False)
    invited_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
