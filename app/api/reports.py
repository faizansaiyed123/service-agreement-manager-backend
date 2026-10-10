from datetime import UTC, date, datetime, timedelta
from decimal import Decimal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, Company, Invoice, Payment, User, WorkOrder
from app.report_schemas import AgreementSummaryRead, BillingReceivablesRead, TechnicianWorkloadRead, WorkOrderReportRead

router = APIRouter(prefix="/reports", tags=["reports"])


def utc_today() -> date:
    return datetime.now(UTC).date()


def count_agreements(db: Session, company_id, *conditions) -> int:
    stmt = select(func.count()).select_from(Agreement).where(
        Agreement.company_id == company_id, *conditions
    )
    return int(db.scalar(stmt) or 0)


@router.get("/agreements/summary", response_model=AgreementSummaryRead)
def agreement_summary(
    as_of: date | None = None,
    expiring_within_days: int = Query(default=30, ge=1, le=365),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> AgreementSummaryRead:
    day = as_of or utc_today()
    last_expiring_day = day + timedelta(days=expiring_within_days)
    current_states = ("accepted", "active", "suspended")
    return AgreementSummaryRead(
        as_of=day,
        expiring_within_days=expiring_within_days,
        active_count=count_agreements(
            db, user.company_id, Agreement.status == "active",
            Agreement.start_date <= day, Agreement.end_date >= day,
        ),
        accepted_future_count=count_agreements(
            db, user.company_id, Agreement.status == "accepted", Agreement.start_date > day,
        ),
        expiring_count=count_agreements(
            db, user.company_id, Agreement.status == "active",
            Agreement.start_date <= day, Agreement.end_date >= day, Agreement.end_date <= last_expiring_day,
        ),
        expired_by_term_count=count_agreements(
            db, user.company_id, Agreement.status.in_(current_states), Agreement.end_date < day,
        ),
        cancelled_count=count_agreements(
            db, user.company_id, Agreement.status == "cancelled",
        ),
        metric_definitions={
            "active_count": "Agreements with status active whose start_date <= as_of <= end_date.",
            "accepted_future_count": "Accepted agreements whose start_date is after as_of.",
            "expiring_count": "Active agreements ending between as_of and as_of + expiring_within_days, inclusive.",
            "expired_by_term_count": "Accepted, active, or suspended agreements whose end_date is before as_of; status is not mutated.",
            "cancelled_count": "Agreements whose recorded status is cancelled.",
        },
    )


@router.get("/billing/receivables", response_model=BillingReceivablesRead)
def billing_receivables(
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> BillingReceivablesRead:
    if invoice_date_from and invoice_date_to and invoice_date_to < invoice_date_from:
        raise DomainError(422, "invalid_date_range", "invoice_date_to must be on or after invoice_date_from")
    company = db.get(Company, user.company_id)
    if company is None:
        raise DomainError(404, "company_not_found", "Company not found")
    paid_subquery = (
        select(Payment.invoice_id, func.sum(Payment.amount).label("paid"))
        .group_by(Payment.invoice_id)
        .subquery()
    )
    stmt = select(Invoice, func.coalesce(paid_subquery.c.paid, 0)).outerjoin(
        paid_subquery, paid_subquery.c.invoice_id == Invoice.id
    ).where(
        Invoice.company_id == user.company_id, Invoice.status != "void",
    )
    if invoice_date_from:
        stmt = stmt.where(Invoice.invoice_date >= invoice_date_from)
    if invoice_date_to:
        stmt = stmt.where(Invoice.invoice_date <= invoice_date_to)
    rows = list(db.execute(stmt).all())
    issued = [(invoice, Decimal(paid or 0)) for invoice, paid in rows if invoice.status in {"issued", "partially_paid", "paid"}]
    drafts = [invoice for invoice, _ in rows if invoice.status == "draft"]
    today = utc_today()
    total_invoiced = sum((invoice.total_amount for invoice, _ in issued), Decimal("0.00"))
    total_paid = sum((min(paid, invoice.total_amount) for invoice, paid in issued), Decimal("0.00"))
    outstanding = sum((max(invoice.total_amount - paid, Decimal("0.00")) for invoice, paid in issued), Decimal("0.00"))
    overdue = [
        (invoice, max(invoice.total_amount - paid, Decimal("0.00")))
        for invoice, paid in issued
        if invoice.status in {"issued", "partially_paid"} and invoice.due_date < today
    ]
    return BillingReceivablesRead(
        as_of=today,
        invoice_date_from=invoice_date_from,
        invoice_date_to=invoice_date_to,
        currency=company.currency,
        issued_invoice_count=len(issued),
        total_invoiced=total_invoiced,
        total_paid=total_paid,
        outstanding=outstanding,
        overdue_invoice_count=len(overdue),
        overdue_amount=sum((balance for _, balance in overdue), Decimal("0.00")),
        draft_invoice_count=len(drafts),
        draft_amount=sum((invoice.total_amount for invoice in drafts), Decimal("0.00")),
    )


@router.get("/work-orders", response_model=WorkOrderReportRead)
def work_order_report(
    as_of: date | None = None,
    scheduled_from: date | None = None,
    scheduled_to: date | None = None,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> WorkOrderReportRead:
    if scheduled_from and scheduled_to and scheduled_to < scheduled_from:
        raise DomainError(422, "invalid_date_range", "scheduled_to must be on or after scheduled_from")
    day = as_of or utc_today()
    stmt = select(WorkOrder.status, func.count()).where(WorkOrder.company_id == user.company_id)
    if scheduled_from:
        stmt = stmt.where(WorkOrder.scheduled_for >= scheduled_from)
    if scheduled_to:
        stmt = stmt.where(WorkOrder.scheduled_for <= scheduled_to)
    status_counts = {status: int(count) for status, count in db.execute(stmt.group_by(WorkOrder.status)).all()}
    overdue_stmt = select(func.count()).select_from(WorkOrder).where(
        WorkOrder.company_id == user.company_id,
        WorkOrder.scheduled_for < day,
        WorkOrder.status.in_(("scheduled", "assigned", "in_progress")),
    )
    if scheduled_from:
        overdue_stmt = overdue_stmt.where(WorkOrder.scheduled_for >= scheduled_from)
    if scheduled_to:
        overdue_stmt = overdue_stmt.where(WorkOrder.scheduled_for <= scheduled_to)

    workload_stmt = select(
        User.id,
        User.full_name,
        func.count(WorkOrder.id).label("assigned_count"),
        func.coalesce(func.sum(case((WorkOrder.status.in_(("scheduled", "assigned", "in_progress")), 1), else_=0)), 0).label("open_count"),
        func.coalesce(func.sum(case((WorkOrder.status == "completed", 1), else_=0)), 0).label("completed_count"),
    ).outerjoin(WorkOrder, and_(
        WorkOrder.assigned_to_user_id == User.id,
        WorkOrder.company_id == user.company_id,
        *([WorkOrder.scheduled_for >= scheduled_from] if scheduled_from else []),
        *([WorkOrder.scheduled_for <= scheduled_to] if scheduled_to else []),
    )).where(
        User.company_id == user.company_id, User.role == "technician", User.is_active.is_(True)
    ).group_by(User.id, User.full_name).order_by(User.full_name)
    technicians = [
        TechnicianWorkloadRead(
            user_id=str(row[0]), full_name=row[1], assigned_count=int(row[2] or 0),
            open_count=int(row[3] or 0), completed_count=int(row[4] or 0),
        )
        for row in db.execute(workload_stmt).all()
    ]
    return WorkOrderReportRead(
        as_of=day, scheduled_from=scheduled_from, scheduled_to=scheduled_to,
        status_counts=status_counts, overdue_open_count=int(db.scalar(overdue_stmt) or 0),
        technicians=technicians,
    )
