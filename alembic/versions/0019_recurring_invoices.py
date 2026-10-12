"""Add recurring invoice schedules."""
from alembic import op
import sqlalchemy as sa

revision = "0019_recurring_invoices"
down_revision = "0018_billing_adjustments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "recurring_invoice_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=True),
        sa.Column("agreement_id", sa.Uuid(), nullable=True),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("frequency", sa.String(24), nullable=False),
        sa.Column("next_invoice_date", sa.Date(), nullable=False),
        sa.Column("due_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("discount_percent", sa.Numeric(5,2), server_default="0", nullable=False),
        sa.Column("tax_percent", sa.Numeric(5,2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("line_templates", sa.JSON(), nullable=False),
        sa.Column("auto_issue", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("last_invoice_id", sa.Uuid(), nullable=True),
        sa.Column("last_run_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_run_error", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["last_invoice_id"], ["invoices.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_recurring_invoice_schedules"),
        sa.UniqueConstraint("company_id","name",name="company_recurring_invoice_name"),
        sa.CheckConstraint("frequency in ('monthly','quarterly','semi_annual','annual')",name="valid_recurring_invoice_frequency"),
        sa.CheckConstraint("due_days between 0 and 365",name="valid_recurring_invoice_due_days"),
        sa.CheckConstraint("discount_percent between 0 and 100",name="recurring_discount_percent_valid"),
        sa.CheckConstraint("tax_percent between 0 and 100",name="recurring_tax_percent_valid"),
    )
    op.create_index("ix_recurring_invoice_schedules_company_id","recurring_invoice_schedules",["company_id"])
    op.create_index("ix_recurring_invoice_schedules_customer_id","recurring_invoice_schedules",["customer_id"])
    op.create_index("ix_recurring_invoice_schedules_next_invoice_date","recurring_invoice_schedules",["next_invoice_date"])


def downgrade() -> None:
    op.drop_index("ix_recurring_invoice_schedules_next_invoice_date",table_name="recurring_invoice_schedules")
    op.drop_index("ix_recurring_invoice_schedules_customer_id",table_name="recurring_invoice_schedules")
    op.drop_index("ix_recurring_invoice_schedules_company_id",table_name="recurring_invoice_schedules")
    op.drop_table("recurring_invoice_schedules")
