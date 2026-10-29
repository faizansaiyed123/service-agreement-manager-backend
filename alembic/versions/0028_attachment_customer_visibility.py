"""Add explicit customer visibility for attachments."""
from alembic import op
import sqlalchemy as sa


revision = "0028_attachment_customer_visibility"
down_revision = "0027_technician_branch_scope"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "attachments",
        sa.Column("customer_visible", sa.Boolean(), nullable=False, server_default=sa.false()),
    )


def downgrade() -> None:
    op.drop_column("attachments", "customer_visible")
