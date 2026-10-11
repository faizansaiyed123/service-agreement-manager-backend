"""Add tenant-scoped attachment metadata."""
from alembic import op
import sqlalchemy as sa

revision = "0015_attachments"
down_revision = "0014_customer_import_idempotency"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "attachments",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("entity_type", sa.String(32), nullable=False),
        sa.Column("entity_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(255), nullable=False),
        sa.Column("content_type", sa.String(255), nullable=False),
        sa.Column("size_bytes", sa.BigInteger(), nullable=False),
        sa.Column("sha256", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(700), nullable=False),
        sa.Column("status", sa.String(24), server_default="active", nullable=False),
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_attachments"),
        sa.UniqueConstraint("company_id", "storage_key", name="company_attachment_storage_key"),
        sa.CheckConstraint(
            "entity_type in ('customer','service_location','equipment','agreement','work_order','invoice')",
            name="valid_attachment_entity_type",
        ),
        sa.CheckConstraint("status in ('active','deleted')", name="valid_attachment_status"),
    )
    op.create_index("ix_attachments_company_id", "attachments", ["company_id"])
    op.create_index("ix_attachments_uploaded_by_user_id", "attachments", ["uploaded_by_user_id"])
    op.create_index("ix_attachments_entity_type", "attachments", ["entity_type"])
    op.create_index("ix_attachments_entity_id", "attachments", ["entity_id"])
    op.create_index("ix_attachments_status", "attachments", ["status"])


def downgrade() -> None:
    op.drop_index("ix_attachments_status", table_name="attachments")
    op.drop_index("ix_attachments_entity_id", table_name="attachments")
    op.drop_index("ix_attachments_entity_type", table_name="attachments")
    op.drop_index("ix_attachments_uploaded_by_user_id", table_name="attachments")
    op.drop_index("ix_attachments_company_id", table_name="attachments")
    op.drop_table("attachments")
