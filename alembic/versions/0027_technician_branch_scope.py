"""Scope existing technicians to their company's active branches."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa


revision = "0027_technician_branch_scope"
down_revision = "0026_customer_team_portal"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("branch_scope_enabled", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    bind = op.get_bind()
    technicians = list(bind.execute(sa.text("SELECT id, company_id FROM users WHERE role = 'technician'")).mappings())
    for technician in technicians:
        branches = list(bind.execute(sa.text(
            "SELECT id FROM company_branches WHERE company_id = :company_id AND is_active = true"
        ), {"company_id": technician["company_id"]}).scalars())
        for branch_id in branches:
            bind.execute(sa.text("""
                INSERT INTO technician_branch_memberships
                    (id, company_id, user_id, branch_id, created_at, updated_at)
                VALUES (:id, :company_id, :user_id, :branch_id, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                ON CONFLICT (company_id, user_id, branch_id) DO NOTHING
            """), {
                "id": str(uuid4()),
                "company_id": technician["company_id"],
                "user_id": technician["id"],
                "branch_id": branch_id,
            })
        bind.execute(sa.text(
            "UPDATE users SET branch_scope_enabled = true WHERE id = :user_id"
        ), {"user_id": technician["id"]})


def downgrade() -> None:
    op.drop_column("users", "branch_scope_enabled")
