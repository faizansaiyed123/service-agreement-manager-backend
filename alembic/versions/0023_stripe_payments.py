"""Add Stripe payment intent tracking columns to payments."""
from alembic import op
import sqlalchemy as sa

revision = "0023_stripe_payments"
down_revision = "0022_email_verification"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("payments", sa.Column("stripe_payment_intent_id", sa.String(64), nullable=True))
    op.create_index("ix_payments_stripe_payment_intent_id", "payments", ["stripe_payment_intent_id"])
    op.add_column("payments", sa.Column("stripe_status", sa.String(32), nullable=True))


def downgrade() -> None:
    op.drop_index("ix_payments_stripe_payment_intent_id", table_name="payments")
    op.drop_column("payments", "stripe_payment_intent_id")
    op.drop_column("payments", "stripe_status")