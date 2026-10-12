"""Ensure every company has a primary HQ branch and backfill dispatch links."""
from uuid import uuid4

from alembic import op
import sqlalchemy as sa

revision = "0021_default_company_branch"
down_revision = "0020_sms_outbox"
branch_labels = None
depends_on = None


def upgrade() -> None:
    bind = op.get_bind()
    companies = list(bind.execute(sa.text("SELECT id, timezone FROM companies")).mappings())
    for company in companies:
        existing = bind.execute(
            sa.text("SELECT id FROM company_branches WHERE company_id = :company_id LIMIT 1"),
            {"company_id": company["id"]},
        ).first()
        if existing:
            continue
        branch_id = str(uuid4())
        bind.execute(
            sa.text("""
                INSERT INTO company_branches
                (id, company_id, name, code, timezone, country_code, is_primary, is_active, created_at, updated_at)
                VALUES
                (:id, :company_id, 'Head Office', 'HQ', :timezone, 'US', true, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
            """),
            {
                "id": branch_id,
                "company_id": company["id"],
                "timezone": company["timezone"] or "UTC",
            },
        )
        for day in range(7):
            bind.execute(
                sa.text("""
                    INSERT INTO branch_business_hours
                    (id, branch_id, day_of_week, is_closed, created_at, updated_at)
                    VALUES
                    (:id, :branch_id, :day, true, CURRENT_TIMESTAMP, CURRENT_TIMESTAMP)
                """),
                {"id": str(uuid4()), "branch_id": branch_id, "day": day},
            )

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
    # Default branches may have gained business data after this migration.
    # Preserve them rather than destructively deleting customer-facing branches.
    pass
