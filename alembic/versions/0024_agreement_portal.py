"""Add electronic agreement portal and rejection state."""
from alembic import op
import sqlalchemy as sa

revision = "0024_agreement_portal"
down_revision = "0023_stripe_payments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("valid_status", "agreements", type_="check")
    op.create_check_constraint(
        "valid_status",
        "agreements",
        "status in ('draft','proposed','accepted','active','suspended','cancelled','expired','rejected')",
    )
    op.add_column("agreements", sa.Column("rejected_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("agreements", sa.Column("rejected_by_name", sa.String(160), nullable=True))
    op.add_column("agreements", sa.Column("rejection_reason", sa.Text(), nullable=True))

    op.create_table(
        "agreement_portal_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), sa.ForeignKey("agreements.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("notification_outbox.id", ondelete="SET NULL"), nullable=True),
        sa.Column("agreement_version", sa.Integer(), nullable=False),
        sa.Column("recipient_name", sa.String(160), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("decision_ip", sa.String(45), nullable=True),
        sa.Column("decision_user_agent", sa.String(1000), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status in ('pending','accepted','rejected','revoked','expired')",
            name="agreement_portal_valid_status",
        ),
    )
    op.create_index(
        "ix_agreement_portal_tokens_company_id",
        "agreement_portal_tokens",
        ["company_id"],
    )
    op.create_index(
        "ix_agreement_portal_tokens_agreement_id",
        "agreement_portal_tokens",
        ["agreement_id"],
    )
    op.create_index(
        "ix_agreement_portal_tokens_status",
        "agreement_portal_tokens",
        ["status"],
    )
    op.create_index(
        "ix_agreement_portal_tokens_expires_at",
        "agreement_portal_tokens",
        ["expires_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_agreement_portal_tokens_expires_at", table_name="agreement_portal_tokens")
    op.drop_index("ix_agreement_portal_tokens_status", table_name="agreement_portal_tokens")
    op.drop_index("ix_agreement_portal_tokens_agreement_id", table_name="agreement_portal_tokens")
    op.drop_index("ix_agreement_portal_tokens_company_id", table_name="agreement_portal_tokens")
    op.drop_table("agreement_portal_tokens")
    op.drop_column("agreements", "rejection_reason")
    op.drop_column("agreements", "rejected_by_name")
    op.drop_column("agreements", "rejected_at")
    op.drop_constraint("valid_status", "agreements", type_="check")
    op.create_check_constraint(
        "valid_status",
        "agreements",
        "status in ('draft','proposed','accepted','active','suspended','cancelled','expired')",
    )
