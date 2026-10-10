"""Limit each company to one primary branch."""
from alembic import op
import sqlalchemy as sa

revision = "0012_primary_branch"
down_revision = "0011_company_branches"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "uq_company_branches_single_primary",
        "company_branches",
        ["company_id"],
        unique=True,
        postgresql_where=sa.text("is_primary"),
        sqlite_where=sa.text("is_primary"),
    )


def downgrade() -> None:
    op.drop_index(
        "uq_company_branches_single_primary",
        table_name="company_branches",
    )
