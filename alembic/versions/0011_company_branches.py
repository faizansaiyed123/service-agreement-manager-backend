"""Add company branches, weekly business hours, and dated closures."""
from alembic import op
import sqlalchemy as sa

revision = "0011_company_branches"
down_revision = "0010_password_recovery"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "company_branches",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("code", sa.String(32), nullable=False),
        sa.Column("timezone", sa.String(64), server_default="UTC", nullable=False),
        sa.Column("address_line1", sa.String(180), nullable=True),
        sa.Column("address_line2", sa.String(180), nullable=True),
        sa.Column("city", sa.String(100), nullable=True),
        sa.Column("region", sa.String(100), nullable=True),
        sa.Column("postal_code", sa.String(24), nullable=True),
        sa.Column("country_code", sa.String(2), server_default="US", nullable=False),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("email", sa.String(320), nullable=True),
        sa.Column("is_primary", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(code) > 0", name="ck_company_branches_nonempty_code"),
        sa.ForeignKeyConstraint(
            ["company_id"], ["companies.id"],
            name="fk_company_branches_company_id_companies", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_company_branches"),
        sa.UniqueConstraint("company_id", "code", name="company_branch_code"),
    )
    op.create_index("ix_company_branches_company_id", "company_branches", ["company_id"])

    op.create_table(
        "branch_business_hours",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("day_of_week", sa.Integer(), nullable=False),
        sa.Column("is_closed", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("opens_at", sa.Time(), nullable=True),
        sa.Column("closes_at", sa.Time(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("day_of_week between 0 and 6", name="ck_branch_business_hours_valid_day_of_week"),
        sa.CheckConstraint(
            "((is_closed = true and opens_at is null and closes_at is null) or "
            "(is_closed = false and opens_at is not null and closes_at is not null and closes_at > opens_at))",
            name="ck_branch_business_hours_valid_hours_window",
        ),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["company_branches.id"],
            name="fk_branch_business_hours_branch_id_company_branches", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_branch_business_hours"),
        sa.UniqueConstraint("branch_id", "day_of_week", name="branch_business_hours_day"),
    )
    op.create_index("ix_branch_business_hours_branch_id", "branch_business_hours", ["branch_id"])

    op.create_table(
        "branch_closures",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("branch_id", sa.Uuid(), nullable=False),
        sa.Column("closure_date", sa.Date(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("length(name) > 0", name="ck_branch_closures_nonempty_name"),
        sa.ForeignKeyConstraint(
            ["branch_id"], ["company_branches.id"],
            name="fk_branch_closures_branch_id_company_branches", ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id", name="pk_branch_closures"),
        sa.UniqueConstraint("branch_id", "closure_date", name="branch_closure_date"),
    )
    op.create_index("ix_branch_closures_branch_id", "branch_closures", ["branch_id"])
    op.create_index("ix_branch_closures_closure_date", "branch_closures", ["closure_date"])


def downgrade() -> None:
    op.drop_index("ix_branch_closures_closure_date", table_name="branch_closures")
    op.drop_index("ix_branch_closures_branch_id", table_name="branch_closures")
    op.drop_table("branch_closures")
    op.drop_index("ix_branch_business_hours_branch_id", table_name="branch_business_hours")
    op.drop_table("branch_business_hours")
    op.drop_index("ix_company_branches_company_id", table_name="company_branches")
    op.drop_table("company_branches")
