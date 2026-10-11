"""Add customer import request idempotency metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0014_customer_import_idempotency"
down_revision = "0013_customer_imports"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "customer_import_jobs",
        sa.Column("idempotency_key", sa.String(255), nullable=True),
    )
    op.add_column(
        "customer_import_jobs",
        sa.Column("request_hash", sa.String(64), nullable=True),
    )
    op.create_unique_constraint(
        "customer_import_job_idempotency",
        "customer_import_jobs",
        ["company_id", "idempotency_key"],
    )


def downgrade() -> None:
    op.drop_constraint(
        "customer_import_job_idempotency",
        "customer_import_jobs",
        type_="unique",
    )
    op.drop_column("customer_import_jobs", "request_hash")
    op.drop_column("customer_import_jobs", "idempotency_key")
