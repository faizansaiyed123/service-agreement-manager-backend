import logging
import time
from datetime import UTC, date, datetime
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.errors import DomainError
from app.db.session import SessionLocal
from app.models import MaintenanceSchedule, WorkOrder
from app.services.maintenance import (
    add_order_event,
    create_work_order_number,
    next_occurrence,
    validate_context,
)

logger = logging.getLogger(__name__)
SessionFactory = callable
DEFAULT_BATCH_SIZE = 100
DEFAULT_MAX_OCCURRENCES_PER_SCHEDULE = 3


def run_once(
    session_factory=SessionLocal,
    *,
    as_of: date | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    max_occurrences_per_schedule: int = DEFAULT_MAX_OCCURRENCES_PER_SCHEDULE,
) -> dict[str, int]:
    """Generate due maintenance work orders using DB locks and bounded catch-up."""
    if batch_size < 1 or max_occurrences_per_schedule < 1:
        raise ValueError("batch_size and max_occurrences_per_schedule must be positive")
    current_day = as_of or datetime.now(UTC).date()
    result = {"scanned": 0, "generated": 0, "failed": 0, "skipped": 0}
    db: Session = session_factory()
    try:
        due_schedules = list(db.scalars(
            select(MaintenanceSchedule)
            .where(
                MaintenanceSchedule.is_active.is_(True),
                MaintenanceSchedule.next_due_date <= current_day,
            )
            .order_by(MaintenanceSchedule.next_due_date, MaintenanceSchedule.id)
            .with_for_update(skip_locked=True)
            .limit(batch_size)
        ).all())
        result["scanned"] = len(due_schedules)

        for schedule in due_schedules:
            for _ in range(max_occurrences_per_schedule):
                occurrence = schedule.next_due_date
                if not schedule.is_active or occurrence > current_day:
                    break
                schedule.last_generation_attempt_at = datetime.now(UTC)
                try:
                    already_exists = False
                    with db.begin_nested():
                        existing = db.scalar(select(WorkOrder).where(
                            WorkOrder.maintenance_schedule_id == schedule.id,
                            WorkOrder.occurrence_date == occurrence,
                        ))
                        if existing is not None:
                            # Recover a schedule whose occurrence exists but whose cursor was not advanced.
                            schedule.next_due_date = next_occurrence(occurrence, schedule.frequency)
                            schedule.last_generation_error = None
                            db.flush()
                            already_exists = True
                        else:
                            validate_context(
                                db,
                                schedule.company_id,
                                schedule.customer_id,
                                schedule.service_location_id,
                                schedule.equipment_id,
                                schedule.agreement_id,
                                occurrence,
                            )
                            work_order = WorkOrder(
                                company_id=schedule.company_id,
                                customer_id=schedule.customer_id,
                                service_location_id=schedule.service_location_id,
                                equipment_id=schedule.equipment_id,
                                agreement_id=schedule.agreement_id,
                                maintenance_schedule_id=schedule.id,
                                occurrence_date=occurrence,
                                work_order_number=create_work_order_number(db, schedule.company_id),
                                title=schedule.name,
                                description=schedule.description,
                                priority="normal",
                                scheduled_for=occurrence,
                                status="scheduled",
                            )
                            db.add(work_order)
                            db.flush()
                            add_order_event(
                                db,
                                work_order,
                                schedule.created_by or UUID(int=0),
                                "work_order.generated_by_scheduler",
                                detail={
                                    "schedule_id": str(schedule.id),
                                    "occurrence_date": occurrence.isoformat(),
                                },
                            )
                            schedule.next_due_date = next_occurrence(occurrence, schedule.frequency)
                            schedule.last_generation_error = None
                            db.flush()
                    if already_exists:
                        result["skipped"] += 1
                    else:
                        result["generated"] += 1
                except DomainError as exc:
                    schedule.last_generation_error = f"{exc.code}: {exc.message}"[:1000]
                    result["failed"] += 1
                    logger.warning(
                        "Maintenance generation failed for schedule %s: %s",
                        schedule.id,
                        exc.code,
                    )
                    break
                except IntegrityError:
                    # Savepoint rollback leaves the outer transaction usable.
                    existing = db.scalar(select(WorkOrder).where(
                        WorkOrder.maintenance_schedule_id == schedule.id,
                        WorkOrder.occurrence_date == occurrence,
                    ))
                    if existing is not None:
                        schedule.next_due_date = next_occurrence(occurrence, schedule.frequency)
                        schedule.last_generation_error = None
                        result["skipped"] += 1
                        continue
                    schedule.last_generation_error = (
                        "database_conflict: a unique-key conflict prevented work-order generation"
                    )
                    result["failed"] += 1
                    logger.warning(
                        "Maintenance generation encountered a database conflict for schedule %s",
                        schedule.id,
                    )
                    break
        db.commit()
        return result
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def run_forever(*, poll_seconds: int = 60, batch_size: int = DEFAULT_BATCH_SIZE) -> None:
    if poll_seconds < 1:
        raise ValueError("poll_seconds must be positive")
    while True:
        try:
            outcome = run_once(batch_size=batch_size)
            if outcome["scanned"]:
                logger.info("Maintenance worker run completed: %s", outcome)
        except KeyboardInterrupt:
            logger.info("Maintenance worker shutting down")
            return
        except Exception:
            logger.exception("Maintenance worker iteration failed")
        time.sleep(poll_seconds)


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    run_forever()
