"""Initial identity and customer domain tables."""
from alembic import op
import sqlalchemy as sa

revision = "0001_initial"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "companies",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("legal_name", sa.String(200), nullable=True),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("currency", sa.String(3), server_default="USD", nullable=False),
        sa.Column("customer_sequence", sa.Integer(), server_default="0", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.PrimaryKeyConstraint("id", name="pk_companies"),
    )
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False), sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False), sa.Column("role", sa.String(24), server_default="staff", nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("role in ('owner','admin','manager','technician','billing','staff')", name="ck_users_valid_role"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_users_company_id_companies", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_users"), sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_company_id", "users", ["company_id"], unique=False)
    op.create_table(
        "auth_sessions",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("refresh_jti", sa.String(64), nullable=False), sa.Column("expires_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], name="fk_auth_sessions_user_id_users", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_auth_sessions"), sa.UniqueConstraint("refresh_jti", name="uq_auth_sessions_refresh_jti"),
    )
    op.create_index("ix_auth_sessions_user_id", "auth_sessions", ["user_id"], unique=False)
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_number", sa.String(32), nullable=False), sa.Column("kind", sa.String(24), server_default="residential", nullable=False),
        sa.Column("name", sa.String(180), nullable=False), sa.Column("email", sa.String(320), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True), sa.Column("status", sa.String(20), server_default="active", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True), sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_customers_company_id_companies", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_customers"),
        sa.UniqueConstraint("company_id", "customer_number", name="customer_company_number"),
    )
    op.create_index("ix_customers_company_id", "customers", ["company_id"], unique=False)
    op.create_table(
        "contacts",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False), sa.Column("full_name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(320), nullable=True), sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("is_billing_contact", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_contacts_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_contacts_customer_id_customers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_contacts"),
    )
    op.create_index("ix_contacts_company_id", "contacts", ["company_id"], unique=False)
    op.create_index("ix_contacts_customer_id", "contacts", ["customer_id"], unique=False)
    op.create_table(
        "service_locations",
        sa.Column("id", sa.Uuid(), nullable=False), sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False), sa.Column("name", sa.String(120), nullable=False),
        sa.Column("address_line1", sa.String(180), nullable=False), sa.Column("address_line2", sa.String(180), nullable=True),
        sa.Column("city", sa.String(100), nullable=False), sa.Column("region", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(24), nullable=True), sa.Column("country_code", sa.String(2), server_default="US", nullable=False),
        sa.Column("access_instructions", sa.Text(), nullable=True), sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_service_locations_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_service_locations_customer_id_customers", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_service_locations"),
    )
    op.create_index("ix_service_locations_company_id", "service_locations", ["company_id"], unique=False)
    op.create_index("ix_service_locations_customer_id", "service_locations", ["customer_id"], unique=False)


def downgrade() -> None:
    op.drop_table("service_locations")
    op.drop_table("contacts")
    op.drop_table("customers")
    op.drop_table("auth_sessions")
    op.drop_table("users")
    op.drop_table("companies")
