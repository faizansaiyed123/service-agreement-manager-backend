"""Add agreement lifecycle, immutable proposal snapshots, and audit history."""
from alembic import op
import sqlalchemy as sa

revision = "0003_agreements"
down_revision = "0002_assets_catalog"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("agreement_sequence", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "agreements",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=False),
        sa.Column("agreement_number", sa.String(32), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("status", sa.String(24), server_default="draft", nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("billing_frequency", sa.String(24), server_default="annual", nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("auto_renew", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("renewal_notice_days", sa.Integer(), server_default="30", nullable=False),
        sa.Column("terms_text", sa.Text(), server_default="", nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), server_default="0.00", nullable=False),
        sa.Column("accepted_by_name", sa.String(160), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_method", sa.String(24), nullable=True),
        sa.Column("acceptance_reference", sa.String(255), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("version_number", sa.Integer(), server_default="0", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('draft','proposed','accepted','active','suspended','cancelled','expired')", name="ck_agreements_valid_status"),
        sa.CheckConstraint("billing_frequency in ('monthly','quarterly','semi_annual','annual','one_time')", name="ck_agreements_valid_billing_frequency"),
        sa.CheckConstraint("total_amount >= 0", name="ck_agreements_nonnegative_total"),
        sa.CheckConstraint("renewal_notice_days >= 0", name="ck_agreements_nonnegative_notice_days"),
        sa.CheckConstraint("end_date >= start_date", name="ck_agreements_end_after_start"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_agreements_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_agreements_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], name="fk_agreements_service_location_id_service_locations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_agreements"),
        sa.UniqueConstraint("company_id", "agreement_number", name="company_agreement_number"),
    )
    op.create_index("ix_agreements_company_id", "agreements", ["company_id"])
    op.create_index("ix_agreements_customer_id", "agreements", ["customer_id"])
    op.create_index("ix_agreements_status", "agreements", ["status"])
    op.create_table(
        "agreement_lines",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("catalog_item_id", sa.Uuid(), nullable=True),
        sa.Column("service_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("quantity", sa.Numeric(10, 2), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("line_total", sa.Numeric(14, 2), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_agreement_lines_positive_quantity"),
        sa.CheckConstraint("unit_price >= 0", name="ck_agreement_lines_nonnegative_price"),
        sa.CheckConstraint("line_total >= 0", name="ck_agreement_lines_nonnegative_line_total"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_agreement_lines_agreement_id_agreements", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["catalog_item_id"], ["service_catalog_items.id"], name="fk_agreement_lines_catalog_item_id_service_catalog_items", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_agreement_lines"),
    )
    op.create_index("ix_agreement_lines_agreement_id", "agreement_lines", ["agreement_id"])
    op.create_table(
        "agreement_versions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("version_number", sa.Integer(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("change_reason", sa.String(200), nullable=False),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("version_number > 0", name="ck_agreement_versions_positive_version_number"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_agreement_versions_agreement_id_agreements", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_agreement_versions_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_agreement_versions"),
        sa.UniqueConstraint("agreement_id", "version_number", name="agreement_version_number"),
    )
    op.create_index("ix_agreement_versions_agreement_id", "agreement_versions", ["agreement_id"])
    op.create_table(
        "agreement_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("agreement_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_agreement_events_agreement_id_agreements", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_agreement_events_actor_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_agreement_events"),
    )
    op.create_index("ix_agreement_events_agreement_id", "agreement_events", ["agreement_id"])


def downgrade() -> None:
    op.drop_table("agreement_events")
    op.drop_index("ix_agreement_versions_agreement_id", table_name="agreement_versions")
    op.drop_table("agreement_versions")
    op.drop_index("ix_agreement_lines_agreement_id", table_name="agreement_lines")
    op.drop_table("agreement_lines")
    op.drop_index("ix_agreements_status", table_name="agreements")
    op.drop_index("ix_agreements_customer_id", table_name="agreements")
    op.drop_index("ix_agreements_company_id", table_name="agreements")
    op.drop_table("agreements")
    op.drop_column("companies", "agreement_sequence")
