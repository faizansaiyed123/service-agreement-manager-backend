"""Add durable email notification outbox and delivery attempts."""
from alembic import op
import sqlalchemy as sa

revision = "0007_notifications"
down_revision = "0006_renewals"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "notification_outbox",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(64), nullable=False),
        sa.Column("channel", sa.String(16), server_default="email", nullable=False),
        sa.Column("recipient_email", sa.String(320), nullable=False),
        sa.Column("subject", sa.String(250), nullable=False),
        sa.Column("body", sa.Text(), nullable=False),
        sa.Column("payload", sa.JSON(), server_default=sa.text("'{}'"), nullable=False),
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
        sa.CheckConstraint("channel in ('email')", name="ck_notification_outbox_supported_channel"),
        sa.CheckConstraint("status in ('queued','processing','sent','dead')", name="ck_notification_outbox_valid_status"),
        sa.CheckConstraint("attempt_count >= 0 and max_attempts between 1 and 10", name="ck_notification_outbox_valid_attempt_limits"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_notification_outbox_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], name="fk_notification_outbox_created_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_notification_outbox"),
        sa.UniqueConstraint("company_id", "idempotency_key", name="notification_company_idempotency_key"),
    )
    op.create_index("ix_notification_outbox_company_id", "notification_outbox", ["company_id"])
    op.create_index("ix_notification_outbox_status", "notification_outbox", ["status"])
    op.create_index("ix_notification_outbox_next_attempt_at", "notification_outbox", ["next_attempt_at"])

    op.create_table(
        "notification_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("notification_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="started", nullable=False),
        sa.Column("provider", sa.String(40), server_default="smtp", nullable=False),
        sa.Column("provider_message_id", sa.String(255), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("attempt_number > 0", name="ck_notification_attempts_positive_attempt_number"),
        sa.CheckConstraint("status in ('started','sent','failed')", name="ck_notification_attempts_valid_status"),
        sa.ForeignKeyConstraint(["notification_id"], ["notification_outbox.id"], name="fk_notification_attempts_notification_id_notification_outbox", ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_notification_attempts"),
        sa.UniqueConstraint("notification_id", "attempt_number", name="notification_attempt_number"),
    )
    op.create_index("ix_notification_attempts_notification_id", "notification_attempts", ["notification_id"])


def downgrade() -> None:
    op.drop_index("ix_notification_attempts_notification_id", table_name="notification_attempts")
    op.drop_table("notification_attempts")
    op.drop_index("ix_notification_outbox_next_attempt_at", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_status", table_name="notification_outbox")
    op.drop_index("ix_notification_outbox_company_id", table_name="notification_outbox")
    op.drop_table("notification_outbox")
