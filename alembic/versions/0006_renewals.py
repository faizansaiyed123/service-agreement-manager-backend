"""Store explicit agreement renewal offers and immutable terms snapshots."""
from alembic import op
import sqlalchemy as sa

revision = "0006_renewals"
down_revision = "0005_billing"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "agreement_renewals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("source_agreement_id", sa.Uuid(), nullable=False),
        sa.Column("renewed_agreement_id", sa.Uuid(), nullable=True),
        sa.Column("offered_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("status", sa.String(24), server_default="offered", nullable=False),
        sa.Column("proposed_start_date", sa.Date(), nullable=False),
        sa.Column("proposed_end_date", sa.Date(), nullable=False),
        sa.Column("expires_on", sa.Date(), nullable=False),
        sa.Column("snapshot", sa.JSON(), nullable=False),
        sa.Column("accepted_by_name", sa.String(160), nullable=True),
        sa.Column("accepted_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("acceptance_method", sa.String(24), nullable=True),
        sa.Column("acceptance_reference", sa.String(255), nullable=True),
        sa.Column("decline_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('offered','accepted','declined','expired','cancelled')", name="ck_agreement_renewals_valid_status"),
        sa.CheckConstraint("proposed_end_date >= proposed_start_date", name="ck_agreement_renewals_end_after_start"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_agreement_renewals_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["source_agreement_id"], ["agreements.id"], name="fk_agreement_renewals_source_agreement_id_agreements", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["renewed_agreement_id"], ["agreements.id"], name="fk_agreement_renewals_renewed_agreement_id_agreements", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["offered_by_user_id"], ["users.id"], name="fk_agreement_renewals_offered_by_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_agreement_renewals"),
        sa.UniqueConstraint("renewed_agreement_id", name="unique_successor_agreement"),
    )
    op.create_index("ix_agreement_renewals_company_id", "agreement_renewals", ["company_id"])
    op.create_index("ix_agreement_renewals_source_agreement_id", "agreement_renewals", ["source_agreement_id"])
    op.create_index("ix_agreement_renewals_status", "agreement_renewals", ["status"])


def downgrade() -> None:
    op.drop_index("ix_agreement_renewals_status", table_name="agreement_renewals")
    op.drop_index("ix_agreement_renewals_source_agreement_id", table_name="agreement_renewals")
    op.drop_index("ix_agreement_renewals_company_id", table_name="agreement_renewals")
    op.drop_table("agreement_renewals")
