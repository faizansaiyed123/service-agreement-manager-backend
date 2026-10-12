"""Link maintenance and work-order dispatch to company branches."""
from alembic import op
import sqlalchemy as sa

revision = "0017_branch_dispatch"
down_revision = "0016_webhooks"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("maintenance_schedules", sa.Column("branch_id", sa.Uuid(), nullable=True))
    op.add_column("work_orders", sa.Column("branch_id", sa.Uuid(), nullable=True))
    op.create_index("ix_maintenance_schedules_branch_id", "maintenance_schedules", ["branch_id"])
    op.create_index("ix_work_orders_branch_id", "work_orders", ["branch_id"])
    op.create_foreign_key(
        "fk_maintenance_schedules_branch_id_company_branches",
        "maintenance_schedules",
        "company_branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    op.create_foreign_key(
        "fk_work_orders_branch_id_company_branches",
        "work_orders",
        "company_branches",
        ["branch_id"],
        ["id"],
        ondelete="RESTRICT",
    )
    bind = op.get_bind()
    bind.execute(sa.text("""
        UPDATE maintenance_schedules ms
        SET branch_id = cb.id
        FROM company_branches cb
        WHERE cb.company_id = ms.company_id
          AND cb.is_primary = true
          AND cb.is_active = true
          AND ms.branch_id IS NULL
    """))
    bind.execute(sa.text("""
        UPDATE work_orders wo
        SET branch_id = cb.id
        FROM company_branches cb
        WHERE cb.company_id = wo.company_id
          AND cb.is_primary = true
          AND cb.is_active = true
          AND wo.branch_id IS NULL
    """))


def downgrade() -> None:
    op.drop_constraint("fk_work_orders_branch_id_company_branches", "work_orders", type_="foreignkey")
    op.drop_constraint("fk_maintenance_schedules_branch_id_company_branches", "maintenance_schedules", type_="foreignkey")
    op.drop_index("ix_work_orders_branch_id", table_name="work_orders")
    op.drop_index("ix_maintenance_schedules_branch_id", table_name="maintenance_schedules")
    op.drop_column("work_orders", "branch_id")
    op.drop_column("maintenance_schedules", "branch_id")
