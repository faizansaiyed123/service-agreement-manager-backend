"""Persist recoverable customer bulk imports."""
from alembic import op
import sqlalchemy as sa

revision = "0013_customer_imports"
down_revision = "0012_primary_branch"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "customer_import_jobs",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("status", sa.String(24), server_default="processing", nullable=False),
        sa.Column("total_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("imported_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("failed_rows", sa.Integer(), server_default="0", nullable=False),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_customer_import_jobs"),
    )
    op.create_index("ix_customer_import_jobs_company_id", "customer_import_jobs", ["company_id"])
    op.create_index("ix_customer_import_jobs_created_by_user_id", "customer_import_jobs", ["created_by_user_id"])

    op.create_table(
        "customer_import_rows",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("job_id", sa.Uuid(), nullable=False),
        sa.Column("row_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(24), server_default="pending", nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["job_id"], ["customer_import_jobs.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_customer_import_rows"),
        sa.UniqueConstraint("job_id", "row_number", name="customer_import_row_number"),
    )
    op.create_index("ix_customer_import_rows_job_id", "customer_import_rows", ["job_id"])
    op.create_index("ix_customer_import_rows_customer_id", "customer_import_rows", ["customer_id"])


def downgrade() -> None:
    op.drop_index("ix_customer_import_rows_customer_id", table_name="customer_import_rows")
    op.drop_index("ix_customer_import_rows_job_id", table_name="customer_import_rows")
    op.drop_table("customer_import_rows")
    op.drop_index("ix_customer_import_jobs_created_by_user_id", table_name="customer_import_jobs")
    op.drop_index("ix_customer_import_jobs_company_id", table_name="customer_import_jobs")
    op.drop_table("customer_import_jobs")
