"""Add technician onboarding, dispatch profiles, and customer portal accounts."""
from alembic import op
import sqlalchemy as sa


revision = "0026_customer_team_portal"
down_revision = "0025_invoice_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("maintenance_schedules", sa.Column("required_skill", sa.String(length=80), nullable=True))
    op.add_column("work_orders", sa.Column("required_skill", sa.String(length=80), nullable=True))

    op.create_table(
        "team_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("branch_ids", sa.JSON(), nullable=False),
        sa.Column("skills", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('pending','accepted','revoked','expired')", name="valid_status"),
    )
    op.create_index("ix_team_invitations_company_id", "team_invitations", ["company_id"])
    op.create_index("ix_team_invitations_email", "team_invitations", ["email"])
    op.create_index("ix_team_invitations_status", "team_invitations", ["status"])

    op.create_table(
        "technician_skills",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("skill_name", sa.String(length=80), nullable=False),
        sa.Column("normalized_skill", sa.String(length=80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "user_id", "normalized_skill", name="technician_skill_unique"),
    )
    op.create_index("ix_technician_skills_company_id", "technician_skills", ["company_id"])
    op.create_index("ix_technician_skills_user_id", "technician_skills", ["user_id"])

    op.create_table(
        "technician_branch_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("company_branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("company_id", "user_id", "branch_id", name="technician_branch_unique"),
    )
    op.create_index("ix_technician_branch_memberships_company_id", "technician_branch_memberships", ["company_id"])
    op.create_index("ix_technician_branch_memberships_user_id", "technician_branch_memberships", ["user_id"])
    op.create_index("ix_technician_branch_memberships_branch_id", "technician_branch_memberships", ["branch_id"])

    op.create_table(
        "customer_portal_identities",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False, unique=True),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_portal_identities_email", "customer_portal_identities", ["email"])

    op.create_table(
        "customer_portal_sessions",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("portal_user_id", sa.Uuid(), sa.ForeignKey("customer_portal_identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("refresh_jti", sa.String(length=64), nullable=False, unique=True),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_customer_portal_sessions_portal_user_id", "customer_portal_sessions", ["portal_user_id"])

    op.create_table(
        "customer_portal_memberships",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("portal_user_id", sa.Uuid(), sa.ForeignKey("customer_portal_identities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.UniqueConstraint("portal_user_id", "company_id", "customer_id", name="customer_portal_membership_unique"),
    )
    op.create_index("ix_customer_portal_memberships_portal_user_id", "customer_portal_memberships", ["portal_user_id"])
    op.create_index("ix_customer_portal_memberships_company_id", "customer_portal_memberships", ["company_id"])
    op.create_index("ix_customer_portal_memberships_customer_id", "customer_portal_memberships", ["customer_id"])

    op.create_table(
        "customer_portal_invitations",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("customer_id", sa.Uuid(), sa.ForeignKey("customers.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invited_by_user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("email", sa.String(length=320), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("token_hash", sa.String(length=64), nullable=False, unique=True),
        sa.Column("status", sa.String(length=16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('pending','accepted','revoked','expired')", name="valid_status"),
    )
    op.create_index("ix_customer_portal_invitations_company_id", "customer_portal_invitations", ["company_id"])
    op.create_index("ix_customer_portal_invitations_customer_id", "customer_portal_invitations", ["customer_id"])
    op.create_index("ix_customer_portal_invitations_email", "customer_portal_invitations", ["email"])
    op.create_index("ix_customer_portal_invitations_status", "customer_portal_invitations", ["status"])


def downgrade() -> None:
    op.drop_index("ix_customer_portal_invitations_status", table_name="customer_portal_invitations")
    op.drop_index("ix_customer_portal_invitations_email", table_name="customer_portal_invitations")
    op.drop_index("ix_customer_portal_invitations_customer_id", table_name="customer_portal_invitations")
    op.drop_index("ix_customer_portal_invitations_company_id", table_name="customer_portal_invitations")
    op.drop_table("customer_portal_invitations")
    op.drop_index("ix_customer_portal_memberships_customer_id", table_name="customer_portal_memberships")
    op.drop_index("ix_customer_portal_memberships_company_id", table_name="customer_portal_memberships")
    op.drop_index("ix_customer_portal_memberships_portal_user_id", table_name="customer_portal_memberships")
    op.drop_table("customer_portal_memberships")
    op.drop_index("ix_customer_portal_sessions_portal_user_id", table_name="customer_portal_sessions")
    op.drop_table("customer_portal_sessions")
    op.drop_index("ix_customer_portal_identities_email", table_name="customer_portal_identities")
    op.drop_table("customer_portal_identities")
    op.drop_index("ix_technician_branch_memberships_branch_id", table_name="technician_branch_memberships")
    op.drop_index("ix_technician_branch_memberships_user_id", table_name="technician_branch_memberships")
    op.drop_index("ix_technician_branch_memberships_company_id", table_name="technician_branch_memberships")
    op.drop_table("technician_branch_memberships")
    op.drop_index("ix_technician_skills_user_id", table_name="technician_skills")
    op.drop_index("ix_technician_skills_company_id", table_name="technician_skills")
    op.drop_table("technician_skills")
    op.drop_index("ix_team_invitations_status", table_name="team_invitations")
    op.drop_index("ix_team_invitations_email", table_name="team_invitations")
    op.drop_index("ix_team_invitations_company_id", table_name="team_invitations")
    op.drop_table("team_invitations")
    op.drop_column("work_orders", "required_skill")
    op.drop_column("maintenance_schedules", "required_skill")
