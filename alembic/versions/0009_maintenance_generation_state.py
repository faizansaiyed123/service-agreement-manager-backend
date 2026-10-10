"""Track maintenance worker attempts and recoverable errors."""
from alembic import op
import sqlalchemy as sa

revision = "0009_maintenance_generation_state"
down_revision = "0008_agreement_location_index"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "maintenance_schedules",
        sa.Column("last_generation_attempt_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "maintenance_schedules",
        sa.Column("last_generation_error", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("maintenance_schedules", "last_generation_error")
    op.drop_column("maintenance_schedules", "last_generation_attempt_at")
