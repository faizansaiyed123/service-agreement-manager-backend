"""Add equipment and company service catalog."""
from alembic import op
import sqlalchemy as sa

revision = "0002_assets_catalog"
down_revision = "0001_initial"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "equipment",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=False),
        sa.Column("asset_number", sa.String(32), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("manufacturer", sa.String(120), nullable=True),
        sa.Column("model_number", sa.String(120), nullable=True),
        sa.Column("serial_number", sa.String(120), nullable=True),
        sa.Column("installed_on", sa.Date(), nullable=True),
        sa.Column("warranty_expires_on", sa.Date(), nullable=True),
        sa.Column("status", sa.String(24), server_default="active", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('active','inactive','decommissioned')", name="ck_equipment_valid_equipment_status"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_equipment_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_equipment_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], name="fk_equipment_service_location_id_service_locations", ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_equipment"),
        sa.UniqueConstraint("company_id", "asset_number", name="company_asset_number"),
    )
    op.create_index("ix_equipment_company_id", "equipment", ["company_id"])
    op.create_index("ix_equipment_customer_id", "equipment", ["customer_id"])
    op.create_index("ix_equipment_service_location_id", "equipment", ["service_location_id"])

    op.create_table(
        "service_catalog_items",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("service_code", sa.String(32), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("category", sa.String(60), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("unit_price", sa.Numeric(12, 2), server_default="0.00", nullable=False),
        sa.Column("duration_minutes", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("unit_price >= 0", name="ck_service_catalog_items_nonnegative_unit_price"),
        sa.CheckConstraint("duration_minutes >= 0", name="ck_service_catalog_items_nonnegative_duration"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_service_catalog_items_company_id_companies", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_service_catalog_items"),
        sa.UniqueConstraint("company_id", "service_code", name="company_service_code"),
    )
    op.create_index("ix_service_catalog_items_company_id", "service_catalog_items", ["company_id"])


def downgrade() -> None:
    op.drop_table("service_catalog_items")
    op.drop_table("equipment")
