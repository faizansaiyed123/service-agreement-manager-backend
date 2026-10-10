"""Create invoice, invoice-line, payment-ledger and invoice-event tables."""
from alembic import op
import sqlalchemy as sa

revision = "0005_billing"
down_revision = "0004_operations"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("invoice_sequence", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "invoices",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=True),
        sa.Column("agreement_id", sa.Uuid(), nullable=True),
        sa.Column("invoice_number", sa.String(32), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("invoice_date", sa.Date(), nullable=False),
        sa.Column("due_date", sa.Date(), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("subtotal", sa.Numeric(14, 2), server_default="0.00", nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0.00", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("issued_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("voided_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("void_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('draft','issued','partially_paid','paid','void')", name="ck_invoices_valid_status"),
        sa.CheckConstraint("subtotal >= 0 and total_amount >= 0", name="ck_invoices_nonnegative_amounts"),
        sa.CheckConstraint("due_date >= invoice_date", name="ck_invoices_due_date_not_before_invoice"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_invoices_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_invoices_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], name="fk_invoices_service_location_id_service_locations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_invoices_agreement_id_agreements", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_invoices"),
        sa.UniqueConstraint("company_id", "invoice_number", name="company_invoice_number"),
    )
    op.create_index("ix_invoices_company_id", "invoices", ["company_id"])
    op.create_index("ix_invoices_customer_id", "invoices", ["customer_id"])
    op.create_index("ix_invoices_status", "invoices", ["status"])
    op.create_index("ix_invoices_due_date", "invoices", ["due_date"])

    op.create_table(
        "invoice_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("service_code", sa.String(32), nullable=False),
        sa.Column("description", sa.String(240), nullable=False),
        sa.Column("details", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_invoice_lines_positive_quantity"),
        sa.CheckConstraint("unit_price >= 0 and line_total >= 0", name="ck_invoice_lines_nonnegative_line_amounts"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="fk_invoice_lines_invoice_id_invoices", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_lines"),
    )
    op.create_index("ix_invoice_lines_invoice_id", "invoice_lines", ["invoice_id"])

    op.create_table(
        "payments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("payment_method", sa.String(24), nullable=False),
        sa.Column("reference", sa.String(255), nullable=True),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("received_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.CheckConstraint("amount > 0", name="ck_payments_positive_amount"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_payments_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="fk_payments_invoice_id_invoices", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_payments"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="company_idempotency_key"),
    )
    op.create_index("ix_payments_company_id", "payments", ["company_id"])
    op.create_index("ix_payments_invoice_id", "payments", ["invoice_id"])

    op.create_table(
        "invoice_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invoice_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["invoice_id"], ["invoices.id"], name="fk_invoice_events_invoice_id_invoices", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_invoice_events_actor_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_invoice_events"),
    )
    op.create_index("ix_invoice_events_invoice_id", "invoice_events", ["invoice_id"])


def downgrade() -> None:
    op.drop_index("ix_invoice_events_invoice_id", table_name="invoice_events")
    op.drop_table("invoice_events")
    op.drop_index("ix_payments_invoice_id", table_name="payments")
    op.drop_index("ix_payments_company_id", table_name="payments")
    op.drop_table("payments")
    op.drop_index("ix_invoice_lines_invoice_id", table_name="invoice_lines")
    op.drop_table("invoice_lines")
    op.drop_index("ix_invoices_due_date", table_name="invoices")
    op.drop_index("ix_invoices_status", table_name="invoices")
    op.drop_index("ix_invoices_customer_id", table_name="invoices")
    op.drop_index("ix_invoices_company_id", table_name="invoices")
    op.drop_table("invoices")
    op.drop_column("companies", "invoice_sequence")
