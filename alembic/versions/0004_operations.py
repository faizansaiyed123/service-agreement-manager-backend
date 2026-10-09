"""Add maintenance schedules, work orders, and their event history."""
from alembic import op
import sqlalchemy as sa

revision = "0004_operations"
down_revision = "0003_agreements"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("companies", sa.Column("work_order_sequence", sa.Integer(), server_default="0", nullable=False))
    op.create_table(
        "maintenance_schedules",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_id", sa.Uuid(), nullable=True),
        sa.Column("agreement_id", sa.Uuid(), nullable=True),
        sa.Column("created_by", sa.Uuid(), nullable=True),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("frequency", sa.String(24), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("checklist_template", sa.JSON(), server_default=sa.text("'[]'"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("frequency in ('monthly','quarterly','semi_annual','annual')", name="ck_maintenance_schedules_valid_frequency"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_maintenance_schedules_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_maintenance_schedules_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], name="fk_maintenance_schedules_service_location_id_service_locations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], name="fk_maintenance_schedules_equipment_id_equipment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_maintenance_schedules_agreement_id_agreements", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"], name="fk_maintenance_schedules_created_by_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_maintenance_schedules"),
    )
    op.create_index("ix_maintenance_schedules_company_id", "maintenance_schedules", ["company_id"])
    op.create_index("ix_maintenance_schedules_customer_id", "maintenance_schedules", ["customer_id"])
    op.create_index("ix_maintenance_schedules_next_due_date", "maintenance_schedules", ["next_due_date"])

    op.create_table(
        "work_orders",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("company_id", sa.Uuid(), nullable=False),
        sa.Column("customer_id", sa.Uuid(), nullable=False),
        sa.Column("service_location_id", sa.Uuid(), nullable=False),
        sa.Column("equipment_id", sa.Uuid(), nullable=True),
        sa.Column("agreement_id", sa.Uuid(), nullable=True),
        sa.Column("maintenance_schedule_id", sa.Uuid(), nullable=True),
        sa.Column("occurrence_date", sa.Date(), nullable=True),
        sa.Column("work_order_number", sa.String(32), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(24), server_default="scheduled", nullable=False),
        sa.Column("priority", sa.String(24), server_default="normal", nullable=False),
        sa.Column("scheduled_for", sa.Date(), nullable=False),
        sa.Column("appointment_start", sa.DateTime(timezone=True), nullable=True),
        sa.Column("appointment_end", sa.DateTime(timezone=True), nullable=True),
        sa.Column("assigned_to_user_id", sa.Uuid(), nullable=True),
        sa.Column("assigned_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("completion_notes", sa.Text(), nullable=True),
        sa.Column("technician_findings", sa.Text(), nullable=True),
        sa.Column("checklist_results", sa.JSON(), nullable=True),
        sa.Column("customer_signoff_name", sa.String(160), nullable=True),
        sa.Column("cancellation_reason", sa.Text(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("status in ('scheduled','assigned','in_progress','completed','cancelled')", name="ck_work_orders_valid_status"),
        sa.CheckConstraint("priority in ('low','normal','high','emergency')", name="ck_work_orders_valid_priority"),
        sa.CheckConstraint("((appointment_start is null and appointment_end is null) or (appointment_start is not null and appointment_end is not null and appointment_end > appointment_start))", name="ck_work_orders_valid_appointment_window"),
        sa.ForeignKeyConstraint(["company_id"], ["companies.id"], name="fk_work_orders_company_id_companies", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"], name="fk_work_orders_customer_id_customers", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["service_location_id"], ["service_locations.id"], name="fk_work_orders_service_location_id_service_locations", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["equipment_id"], ["equipment.id"], name="fk_work_orders_equipment_id_equipment", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["agreement_id"], ["agreements.id"], name="fk_work_orders_agreement_id_agreements", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["maintenance_schedule_id"], ["maintenance_schedules.id"], name="fk_work_orders_maintenance_schedule_id_maintenance_schedules", ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["assigned_to_user_id"], ["users.id"], name="fk_work_orders_assigned_to_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_work_orders"),
        sa.UniqueConstraint("company_id", "work_order_number", name="company_work_order_number"),
        sa.UniqueConstraint("maintenance_schedule_id", "occurrence_date", name="schedule_occurrence"),
    )
    op.create_index("ix_work_orders_company_id", "work_orders", ["company_id"])
    op.create_index("ix_work_orders_customer_id", "work_orders", ["customer_id"])
    op.create_index("ix_work_orders_maintenance_schedule_id", "work_orders", ["maintenance_schedule_id"])
    op.create_index("ix_work_orders_status", "work_orders", ["status"])
    op.create_index("ix_work_orders_scheduled_for", "work_orders", ["scheduled_for"])

    op.create_table(
        "work_order_events",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("work_order_id", sa.Uuid(), nullable=False),
        sa.Column("actor_user_id", sa.Uuid(), nullable=True),
        sa.Column("event_type", sa.String(60), nullable=False),
        sa.Column("from_status", sa.String(24), nullable=True),
        sa.Column("to_status", sa.String(24), nullable=True),
        sa.Column("detail", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["work_order_id"], ["work_orders.id"], name="fk_work_order_events_work_order_id_work_orders", ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], name="fk_work_order_events_actor_user_id_users", ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id", name="pk_work_order_events"),
    )
    op.create_index("ix_work_order_events_work_order_id", "work_order_events", ["work_order_id"])


def downgrade() -> None:
    op.drop_index("ix_work_order_events_work_order_id", table_name="work_order_events")
    op.drop_table("work_order_events")
    op.drop_index("ix_work_orders_scheduled_for", table_name="work_orders")
    op.drop_index("ix_work_orders_status", table_name="work_orders")
    op.drop_index("ix_work_orders_maintenance_schedule_id", table_name="work_orders")
    op.drop_index("ix_work_orders_customer_id", table_name="work_orders")
    op.drop_index("ix_work_orders_company_id", table_name="work_orders")
    op.drop_table("work_orders")
    op.drop_index("ix_maintenance_schedules_next_due_date", table_name="maintenance_schedules")
    op.drop_index("ix_maintenance_schedules_customer_id", table_name="maintenance_schedules")
    op.drop_index("ix_maintenance_schedules_company_id", table_name="maintenance_schedules")
    op.drop_table("maintenance_schedules")
    op.drop_column("companies", "work_order_sequence")
