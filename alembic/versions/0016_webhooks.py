"""Add tenant-scoped webhook endpoints and durable deliveries."""
from alembic import op
import sqlalchemy as sa

revision = "0016_webhooks"
down_revision = "0015_attachments"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "webhook_endpoints",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("created_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(120), nullable=False),
        sa.Column("url", sa.String(2048), nullable=False),
        sa.Column("secret_ciphertext", sa.Text(), nullable=False),
        sa.Column("subscribed_events", sa.JSON(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.text("true"), nullable=False),
        sa.Column("last_delivery_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("last_delivery_status", sa.String(24), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["created_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_endpoints"),
        sa.UniqueConstraint("company_id", "name", name="company_webhook_name"),
        sa.CheckConstraint("url like 'https://%'", name="https_webhook_url"),
    )
    op.create_index("ix_webhook_endpoints_company_id", "webhook_endpoints", ["company_id"])
    op.create_index("ix_webhook_endpoints_created_by_user_id", "webhook_endpoints", ["created_by_user_id"])
    op.create_index("ix_webhook_endpoints_is_active", "webhook_endpoints", ["is_active"])

    op.create_table(
        "webhook_deliveries",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("endpoint_id", sa.Uuid(), nullable=False),
        sa.Column("event_id", sa.Uuid(), nullable=False),
        sa.Column("event_type", sa.String(100), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=False),
        sa.Column("status", sa.String(24), server_default="queued", nullable=False),
        sa.Column("scheduled_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("next_attempt_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("locked_until", sa.DateTime(timezone=True), nullable=True),
        sa.Column("attempt_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("max_attempts", sa.Integer(), server_default="8", nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("delivered_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["endpoint_id"], ["webhook_endpoints.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_deliveries"),
        sa.UniqueConstraint("endpoint_id", "event_id", name="webhook_endpoint_event"),
        sa.CheckConstraint(
            "status in ('queued','processing','sent','dead','cancelled')",
            name="valid_webhook_delivery_status",
        ),
        sa.CheckConstraint("attempt_count >= 0 and max_attempts between 1 and 20", name="valid_webhook_attempt_limits"),
    )
    op.create_index("ix_webhook_deliveries_company_id", "webhook_deliveries", ["company_id"])
    op.create_index("ix_webhook_deliveries_endpoint_id", "webhook_deliveries", ["endpoint_id"])
    op.create_index("ix_webhook_deliveries_event_type", "webhook_deliveries", ["event_type"])
    op.create_index("ix_webhook_deliveries_status", "webhook_deliveries", ["status"])
    op.create_index("ix_webhook_deliveries_next_attempt_at", "webhook_deliveries", ["next_attempt_at"])

    op.create_table(
        "webhook_delivery_attempts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("delivery_id", sa.Uuid(), nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(16), server_default="started", nullable=False),
        sa.Column("http_status", sa.Integer(), nullable=True),
        sa.Column("response_body", sa.Text(), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["delivery_id"], ["webhook_deliveries.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id", name="pk_webhook_delivery_attempts"),
        sa.UniqueConstraint("delivery_id", "attempt_number", name="webhook_delivery_attempt_number"),
        sa.CheckConstraint("attempt_number > 0", name="positive_webhook_attempt_number"),
        sa.CheckConstraint("status in ('started','sent','failed')", name="valid_webhook_attempt_status"),
    )
    op.create_index("ix_webhook_delivery_attempts_delivery_id", "webhook_delivery_attempts", ["delivery_id"])


def downgrade() -> None:
    op.drop_index("ix_webhook_delivery_attempts_delivery_id", table_name="webhook_delivery_attempts")
    op.drop_table("webhook_delivery_attempts")
    op.drop_index("ix_webhook_deliveries_next_attempt_at", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_status", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_event_type", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_endpoint_id", table_name="webhook_deliveries")
    op.drop_index("ix_webhook_deliveries_company_id", table_name="webhook_deliveries")
    op.drop_table("webhook_deliveries")
    op.drop_index("ix_webhook_endpoints_is_active", table_name="webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_created_by_user_id", table_name="webhook_endpoints")
    op.drop_index("ix_webhook_endpoints_company_id", table_name="webhook_endpoints")
    op.drop_table("webhook_endpoints")
