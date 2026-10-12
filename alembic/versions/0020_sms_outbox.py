"""Add durable SMS outbox and attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0020_sms_outbox"
down_revision = "0019_recurring_invoices"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "sms_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("recipient_phone", sa.String(40), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("idempotency_key", sa.String(128), nullable=False),
        sa.Column("request_fingerprint", sa.String(64), nullable=False),
        sa.Column("status", sa.String(24), server_default="queued", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="5", nullable=False),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("sent_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_sms_outbox"),
        sa.UniqueConstraint("company_id","idempotency_key",name="sms_company_idempotency"),
        sa.CheckConstraint("status in ('queued','processing','sent','dead')",name="valid_sms_status"),
        sa.CheckConstraint("attempt_count >= 0 and max_attempts between 1 and 10",name="valid_sms_attempts"),
    )
    op.create_index("ix_sms_outbox_company_id","sms_outbox",["company_id"])
    op.create_index("ix_sms_outbox_status","sms_outbox",["status"])
    op.create_index("ix_sms_outbox_next_attempt_at","sms_outbox",["next_attempt_at"])

    op.create_table(
        "sms_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("sms_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="started", nullable=False),
        sa.Column("provider", sa.String(40), server_default="http", nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["sms_id"], ["sms_outbox.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_sms_attempts"),
        sa.UniqueConstraint("sms_id","attempt_number",name="sms_attempt_number"),
    )
    op.create_index("ix_sms_attempts_sms_id","sms_attempts",["sms_id"])


def downgrade() -> None:
    op.drop_index("ix_sms_attempts_sms_id",table_name="sms_attempts")
    op.drop_table("sms_attempts")
    op.drop_index("ix_sms_outbox_next_attempt_at",table_name="sms_outbox")
    op.drop_index("ix_sms_outbox_status",table_name="sms_outbox")
    op.drop_index("ix_sms_outbox_company_id",table_name="sms_outbox")
    op.drop_table("sms_outbox")
