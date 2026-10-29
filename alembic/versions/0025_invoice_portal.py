"""Add secure customer invoice payment links."""
from alembic import op
import sqlalchemy as sa


revision = "0025_invoice_portal"
down_revision = "0024_agreement_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "invoice_portal_tokens",
        sa.Column("id", sa.Uuid(), primary_key=True, nullable=False),
        sa.Column("company_id", sa.Uuid(), sa.ForeignKey("companies.id", ondelete="CASCADE"), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), sa.ForeignKey("invoices.id", ondelete="CASCADE"), nullable=False),
        sa.Column("notification_id", sa.Uuid(), sa.ForeignKey("notification_outbox.id", ondelete="SET NULL"), nullable=True),
        sa.Column("recipient_name", sa.String(160), nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("token_hash", sa.String(64), nullable=False, unique=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="pending"),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("used_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_viewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint(
            "status in ('pending','paid','revoked','expired')",
            name="invoice_portal_valid_status",
        ),
    )
    op.create_index("ix_invoice_portal_tokens_company_id", "invoice_portal_tokens", ["company_id"])
    op.create_index("ix_invoice_portal_tokens_invoice_id", "invoice_portal_tokens", ["invoice_id"])
    op.create_index("ix_invoice_portal_tokens_status", "invoice_portal_tokens", ["status"])
    op.create_index("ix_invoice_portal_tokens_expires_at", "invoice_portal_tokens", ["expires_at"])


def downgrade() -> None:
    op.drop_index("ix_invoice_portal_tokens_expires_at", table_name="invoice_portal_tokens")
    op.drop_index("ix_invoice_portal_tokens_status", table_name="invoice_portal_tokens")
    op.drop_index("ix_invoice_portal_tokens_invoice_id", table_name="invoice_portal_tokens")
    op.drop_index("ix_invoice_portal_tokens_company_id", table_name="invoice_portal_tokens")
    op.drop_table("invoice_portal_tokens")
