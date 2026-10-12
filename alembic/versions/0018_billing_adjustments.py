"""Add invoice adjustments, payment refunds and invoice credits."""
from alembic import op
import sqlalchemy as sa

revision = "0018_billing_adjustments"
down_revision = "0017_branch_dispatch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("invoices", sa.Column("discount_percent", sa.Numeric(5, 2), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("discount_amount", sa.Numeric(14, 2), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("tax_percent", sa.Numeric(5, 2), server_default="0", nullable=False))
    op.add_column("invoices", sa.Column("tax_amount", sa.Numeric(14, 2), server_default="0", nullable=False))
    op.create_check_constraint("invoice_discount_percent_valid", "invoices", "discount_percent between 0 and 100")
    op.create_check_constraint("invoice_tax_percent_valid", "invoices", "tax_percent between 0 and 100")

    op.create_table(
        "payment_refunds",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("payment_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("refund_method", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("refunded_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payment_id"], ["payments.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_payment_refunds"),
        sa.UniqueConstraint("company_id","idempotency_key",name="company_refund_idempotency"),
        sa.CheckConstraint("amount > 0", name="positive_refund_amount"),
    )
    op.create_index("ix_payment_refunds_company_id","payment_refunds",["company_id"])
    op.create_index("ix_payment_refunds_payment_id","payment_refunds",["payment_id"])

    op.create_table(
        "invoice_credits",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14,2), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_credits"),
        sa.UniqueConstraint("company_id","idempotency_key",name="company_credit_idempotency"),
        sa.CheckConstraint("amount > 0", name="positive_credit_amount"),
    )
    op.create_index("ix_invoice_credits_company_id","invoice_credits",["company_id"])
    op.create_index("ix_invoice_credits_invoice_id","invoice_credits",["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_credits_invoice_id", table_name="invoice_credits")
    op.drop_index("ix_invoice_credits_company_id", table_name="invoice_credits")
    op.drop_table("invoice_credits")
    op.drop_index("ix_payment_refunds_payment_id", table_name="payment_refunds")
    op.drop_index("ix_payment_refunds_company_id", table_name="payment_refunds")
    op.drop_table("payment_refunds")
    op.drop_constraint("invoice_tax_percent_valid", "invoices", type_="check")
    op.drop_constraint("invoice_discount_percent_valid", "invoices", type_="check")
    op.drop_column("invoices","tax_amount")
    op.drop_column("invoices","tax_percent")
    op.drop_column("invoices","discount_amount")
    op.drop_column("invoices","discount_percent")
