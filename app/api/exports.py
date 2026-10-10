import csv
import io
from datetime import date
from decimal import Decimal
from typing import Any

from fastapi import APIRouter, Depends, Query, Response
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, Customer, Invoice, Payment, User, WorkOrder

router = APIRouter(prefix="/exports", tags=["CSV exports"])
MAX_EXPORT_ROWS = 10000


def csv_safe(value: Any) -> Any:
    """Prevent spreadsheet formula execution in user-controlled text cells."""
    if isinstance(value, str):
        inspected = value.lstrip(" \t\r\n")
        if value[:1] in {"\t", "\r", "\n"} or inspected.startswith(("=", "+", "-", "@")):
            return "'" + value
    return value


def csv_response(filename: str, headers: tuple[str, ...], rows: list[tuple[Any, ...]]) -> Response:
    buffer = io.StringIO(newline="")
    writer = csv.writer(buffer, lineterminator="\r\n")
    writer.writerow(headers)
    for row in rows:
        writer.writerow([csv_safe(value) for value in row])
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


def validate_date_range(start: date | None, end: date | None, start_name: str, end_name: str) -> None:
    if start and end and end < start:
        raise DomainError(422, "invalid_date_range", f"{end_name} must be on or after {start_name}")


def paging(limit: int, offset: int) -> None:
    if limit < 1 or limit > MAX_EXPORT_ROWS:
        raise DomainError(422, "invalid_export_limit", f"limit must be between 1 and {MAX_EXPORT_ROWS}")
    if offset < 0:
        raise DomainError(422, "invalid_export_offset", "offset must be non-negative")


@router.get("/customers.csv")
def export_customers(
    status: str | None = Query(default=None, pattern="^(active|inactive)$"),
    created_from: date | None = None,
    created_to: date | None = None,
    limit: int = Query(default=1000, ge=1, le=MAX_EXPORT_ROWS),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    validate_date_range(created_from, created_to, "created_from", "created_to")
    paging(limit, offset)
    stmt = select(Customer).where(Customer.company_id == user.company_id)
    if status:
        stmt = stmt.where(Customer.status == status)
    if created_from:
        stmt = stmt.where(func.date(Customer.created_at) >= created_from)
    if created_to:
        stmt = stmt.where(func.date(Customer.created_at) <= created_to)
    records = db.scalars(stmt.order_by(Customer.created_at, Customer.id).limit(limit).offset(offset)).all()
    rows = [
        (str(x.id), x.customer_number, x.kind, x.name, x.email or "", x.phone or "", x.status, x.created_at.isoformat())
        for x in records
    ]
    return csv_response("customers.csv", ("id", "customer_number", "kind", "name", "email", "phone", "status", "created_at"), rows)


@router.get("/invoices.csv")
def export_invoices(
    invoice_date_from: date | None = None,
    invoice_date_to: date | None = None,
    status: str | None = Query(default=None, pattern="^(draft|issued|partially_paid|paid|void)$"),
    limit: int = Query(default=1000, ge=1, le=MAX_EXPORT_ROWS),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    validate_date_range(invoice_date_from, invoice_date_to, "invoice_date_from", "invoice_date_to")
    paging(limit, offset)
    paid = select(Payment.invoice_id, func.sum(Payment.amount).label("amount_paid")).where(
        Payment.company_id == user.company_id
    ).group_by(Payment.invoice_id).subquery()
    stmt = select(Invoice, func.coalesce(paid.c.amount_paid, Decimal("0.00"))).outerjoin(
        paid, paid.c.invoice_id == Invoice.id
    ).where(Invoice.company_id == user.company_id)
    if status:
        stmt = stmt.where(Invoice.status == status)
    if invoice_date_from:
        stmt = stmt.where(Invoice.invoice_date >= invoice_date_from)
    if invoice_date_to:
        stmt = stmt.where(Invoice.invoice_date <= invoice_date_to)
    records = db.execute(stmt.order_by(Invoice.invoice_date, Invoice.id).limit(limit).offset(offset)).all()
    rows = []
    for invoice, paid_amount in records:
        amount_paid = min(Decimal(paid_amount or 0), invoice.total_amount)
        balance = max(invoice.total_amount - amount_paid, Decimal("0.00"))
        rows.append((
            str(invoice.id), invoice.invoice_number, str(invoice.customer_id), invoice.status,
            invoice.invoice_date.isoformat(), invoice.due_date.isoformat(), invoice.currency,
            str(invoice.subtotal), str(invoice.total_amount), str(amount_paid), str(balance),
        ))
    headers = ("id", "invoice_number", "customer_id", "status", "invoice_date", "due_date", "currency", "subtotal", "total_amount", "amount_paid", "balance_due")
    return csv_response("invoices.csv", headers, rows)


@router.get("/work-orders.csv")
def export_work_orders(
    scheduled_from: date | None = None,
    scheduled_to: date | None = None,
    status: str | None = Query(default=None, pattern="^(scheduled|assigned|in_progress|completed|cancelled)$"),
    limit: int = Query(default=1000, ge=1, le=MAX_EXPORT_ROWS),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    validate_date_range(scheduled_from, scheduled_to, "scheduled_from", "scheduled_to")
    paging(limit, offset)
    stmt = select(WorkOrder).where(WorkOrder.company_id == user.company_id)
    if status:
        stmt = stmt.where(WorkOrder.status == status)
    if scheduled_from:
        stmt = stmt.where(WorkOrder.scheduled_for >= scheduled_from)
    if scheduled_to:
        stmt = stmt.where(WorkOrder.scheduled_for <= scheduled_to)
    records = db.scalars(stmt.order_by(WorkOrder.scheduled_for, WorkOrder.id).limit(limit).offset(offset)).all()
    rows = [
        (str(x.id), x.work_order_number, str(x.customer_id), str(x.service_location_id), str(x.assigned_to_user_id or ""),
         x.title, x.status, x.priority, x.scheduled_for.isoformat(), x.completed_at.isoformat() if x.completed_at else "")
        for x in records
    ]
    headers = ("id", "work_order_number", "customer_id", "service_location_id", "assigned_to_user_id", "title", "status", "priority", "scheduled_for", "completed_at")
    return csv_response("work-orders.csv", headers, rows)


@router.get("/agreements.csv")
def export_agreements(
    status: str | None = Query(default=None, pattern="^(draft|proposed|accepted|active|suspended|cancelled|expired)$"),
    start_from: date | None = None,
    end_through: date | None = None,
    limit: int = Query(default=1000, ge=1, le=MAX_EXPORT_ROWS),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Response:
    validate_date_range(start_from, end_through, "start_from", "end_through")
    paging(limit, offset)
    stmt = select(Agreement).where(Agreement.company_id == user.company_id)
    if status:
        stmt = stmt.where(Agreement.status == status)
    if start_from:
        stmt = stmt.where(Agreement.start_date >= start_from)
    if end_through:
        stmt = stmt.where(Agreement.end_date <= end_through)
    records = db.scalars(stmt.order_by(Agreement.start_date, Agreement.id).limit(limit).offset(offset)).all()
    rows = [
        (str(x.id), x.agreement_number, str(x.customer_id), x.title, x.status,
         x.start_date.isoformat(), x.end_date.isoformat(), x.currency, str(x.total_amount))
        for x in records
    ]
    headers = ("id", "agreement_number", "customer_id", "title", "status", "start_date", "end_date", "currency", "total_amount")
    return csv_response("agreements.csv", headers, rows)
