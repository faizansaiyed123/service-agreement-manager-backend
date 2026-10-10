"""Add missing index for agreement service-location queries.

Revision ID: 0008_agreement_location_index
Revises: 0007_notifications
"""
from alembic import op

revision = "0008_agreement_location_index"
down_revision = "0007_notifications"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index(
        "ix_agreements_service_location_id",
        "agreements",
        ["service_location_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_agreements_service_location_id", table_name="agreements")
