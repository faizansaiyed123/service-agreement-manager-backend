from datetime import datetime
from uuid import UUID

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, JSON, String, UniqueConstraint, Uuid
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base
from app.models.base import Timestamped, UUIDPrimaryKey


class TeamInvitation(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "team_invitations"
    __table_args__ = (CheckConstraint("status in ('pending','accepted','revoked','expired')", name="valid_status"),)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    invited_by_user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="RESTRICT"), nullable=False)
    email: Mapped[str] = mapped_column(String(320), index=True, nullable=False)
    full_name: Mapped[str] = mapped_column(String(160), nullable=False)
    token_hash: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    branch_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    skills: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    status: Mapped[str] = mapped_column(String(16), default="pending", server_default="pending", nullable=False, index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    accepted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))


class TechnicianSkill(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "technician_skills"
    __table_args__ = (UniqueConstraint("company_id", "user_id", "normalized_skill", name="technician_skill_unique"),)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    skill_name: Mapped[str] = mapped_column(String(80), nullable=False)
    normalized_skill: Mapped[str] = mapped_column(String(80), nullable=False)


class TechnicianBranchMembership(Base, UUIDPrimaryKey, Timestamped):
    __tablename__ = "technician_branch_memberships"
    __table_args__ = (UniqueConstraint("company_id", "user_id", "branch_id", name="technician_branch_unique"),)
    company_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("companies.id", ondelete="CASCADE"), index=True, nullable=False)
    user_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), index=True, nullable=False)
    branch_id: Mapped[UUID] = mapped_column(Uuid(as_uuid=True), ForeignKey("company_branches.id", ondelete="CASCADE"), index=True, nullable=False)
