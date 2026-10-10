import hashlib
import json
from datetime import UTC, date, datetime
from decimal import Decimal, ROUND_HALF_UP
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Query, Response
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user, require_roles
from app.billing_schemas import InvoiceBaseRead, InvoiceCreate, InvoiceEventRead, InvoiceLineInput, InvoiceRead, InvoiceUpdate, PaymentCreate, PaymentRead, VoidInvoice
from app.core.errors import DomainError
from app.db.session import get_db
from app.models import Agreement, Company, Customer, Invoice, InvoiceEvent, InvoiceLine, Payment, ServiceLocation, User

router = APIRouter(prefix="/invoices", tags=["invoicing"])
CENT = Decimal("0.01")
INVOICE_EDIT_ROLES = ("owner", "admin", "manager", "billing", "staff")
INVOICE_ISSUE_ROLES = ("owner", "admin", "manager", "billing")


def utc_today() -> date:
    return datetime.now(UTC).date()


def get_invoice(db: Session, company_id: UUID, invoice_id: UUID, *, lock: bool = False) -> Invoice:
    stmt = select(Invoice).where(Invoice.id == invoice_id, Invoice.company_id == company_id)
    if lock:
        stmt = stmt.with_for_update()
    invoice = db.scalar(stmt)
    if invoice is None:
        raise DomainError(404, "invoice_not_found", "Invoice not found")
    if not invoice.lines:
        db.refresh(invoice, attribute_names=["lines"])
    return invoice


def event(db: Session, invoice: Invoice, user_id: UUID, event_type: str, previous: str | None = None, detail: dict | None = None) -> None:
    db.add(InvoiceEvent(
        invoice_id=invoice.id, actor_user_id=user_id, event_type=event_type,
        from_status=previous, to_status=invoice.status, detail=detail, created_at=datetime.now(UTC),
    ))


def build_line(payload: InvoiceLineInput) -> InvoiceLine:
    total = (payload.quantity * payload.unit_price).quantize(CENT, rounding=ROUND_HALF_UP)
    return InvoiceLine(
        service_code=payload.service_code.upper(), description=payload.description.strip(),
        details=payload.details, quantity=payload.quantity, unit_price=payload.unit_price, line_total=total,
    )


def recalculate(invoice: Invoice) -> None:
    invoice.subtotal = sum((line.line_total for line in invoice.lines), Decimal("0.00")).quantize(CENT)
    # Tax and discounts are deliberately absent until company tax configuration is implemented.
    invoice.total_amount = invoice.subtotal


def invoice_responses(db: Session, invoices: list[Invoice]) -> list[InvoiceRead]:
    if not invoices:
        return []
    invoice_ids = [invoice.id for invoice in invoices]
    payments = db.execute(
        select(Payment.invoice_id, func.sum(Payment.amount))
        .where(Payment.invoice_id.in_(invoice_ids))
        .group_by(Payment.invoice_id)
    ).all()
    paid_by_invoice = {invoice_id: (amount or Decimal("0.00")) for invoice_id, amount in payments}
    result: list[InvoiceRead] = []
    today = utc_today()
    for invoice in invoices:
        base = InvoiceBaseRead.model_validate(invoice).model_dump()
        paid = paid_by_invoice.get(invoice.id, Decimal("0.00"))
        balance = max(invoice.total_amount - paid, Decimal("0.00"))
        base.update(
            amount_paid=paid,
            balance_due=balance,
            is_overdue=invoice.status in {"issued", "partially_paid"} and invoice.due_date < today,
        )
        result.append(InvoiceRead.model_validate(base))
    return result


def invoice_response(db: Session, invoice: Invoice) -> InvoiceRead:
    return invoice_responses(db, [invoice])[0]


def payment_fingerprint(invoice_id: UUID, payload: PaymentCreate) -> str:
    canonical = json.dumps(
        {
            "invoice_id": str(invoice_id), "amount": str(payload.amount),
            "payment_method": payload.payment_method, "reference": payload.reference,
            "notes": payload.notes,
        },
        sort_keys=True, separators=(",", ":"),
    )
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def replay_payment(
    db: Session, company_id: UUID, invoice_id: UUID, key: str, fingerprint: str,
) -> Payment | None:
    existing = db.scalar(select(Payment).where(
        Payment.company_id == company_id, Payment.idempotency_key == key
    ))
    if existing is None:
        return None
    if existing.invoice_id != invoice_id or existing.request_fingerprint != fingerprint:
        raise DomainError(409, "idempotency_key_reused", "This Idempotency-Key was already used for a different payment request")
    return existing


def verify_invoice_references(db: Session, user: User, payload: InvoiceCreate) -> tuple[Customer, UUID | None]:
    customer = db.scalar(select(Customer).where(
        Customer.id == payload.customer_id, Customer.company_id == user.company_id
    ))
    if customer is None or customer.status != "active":
        raise DomainError(404, "customer_not_found", "Active customer not found")
    location_id = payload.service_location_id
    if payload.agreement_id is not None:
        agreement = db.scalar(select(Agreement).where(
            Agreement.id == payload.agreement_id, Agreement.company_id == user.company_id,
            Agreement.customer_id == customer.id, Agreement.status.in_(("accepted", "active", "suspended")),
        ))
        if agreement is None:
            raise DomainError(404, "agreement_not_found", "A matching current agreement was not found")
        if location_id is None:
            location_id = agreement.service_location_id
        elif location_id != agreement.service_location_id:
            raise DomainError(422, "agreement_location_mismatch", "Invoice location must match the linked agreement")
    if location_id is not None:
        location = db.scalar(select(ServiceLocation).where(
            ServiceLocation.id == location_id, ServiceLocation.company_id == user.company_id,
            ServiceLocation.customer_id == customer.id, ServiceLocation.is_active.is_(True),
        ))
        if location is None:
            raise DomainError(404, "service_location_not_found", "Active service location not found for this customer")
    return customer, location_id


@router.post("", response_model=InvoiceRead, status_code=201)
def create_invoice(payload: InvoiceCreate, user: User = Depends(require_roles(*INVOICE_EDIT_ROLES)), db: Session = Depends(get_db)) -> InvoiceRead:
    customer, location_id = verify_invoice_references(db, user, payload)
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    company.invoice_sequence += 1
    invoice = Invoice(
        company_id=user.company_id, customer_id=customer.id, service_location_id=location_id,
        agreement_id=payload.agreement_id, invoice_number=f"INV-{company.invoice_sequence:06d}",
        status="draft", invoice_date=payload.invoice_date, due_date=payload.due_date,
        currency=company.currency, notes=payload.notes,
    )
    db.add(invoice)
    db.flush()
    invoice.lines.extend(build_line(line) for line in payload.lines)
    recalculate(invoice)
    db.flush()
    event(db, invoice, user.id, "invoice.created", detail={"invoice_number": invoice.invoice_number})
    db.commit()
    invoice = get_invoice(db, user.company_id, invoice.id)
    return invoice_response(db, invoice)


@router.get("", response_model=list[InvoiceRead])
def list_invoices(
    status: str | None = Query(default=None, pattern="^(draft|issued|partially_paid|paid|void|overdue)$"),
    customer_id: UUID | None = None,
    due_through: date | None = None,
    limit: int = Query(default=50, ge=1, le=100),
    offset: int = Query(default=0, ge=0),
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[InvoiceRead]:
    stmt = select(Invoice).options(selectinload(Invoice.lines)).where(Invoice.company_id == user.company_id)
    if status == "overdue":
        stmt = stmt.where(Invoice.status.in_(("issued", "partially_paid")), Invoice.due_date < utc_today())
    elif status:
        stmt = stmt.where(Invoice.status == status)
    if customer_id:
        stmt = stmt.where(Invoice.customer_id == customer_id)
    if due_through:
        stmt = stmt.where(Invoice.due_date <= due_through)
    invoices = list(db.scalars(stmt.order_by(Invoice.invoice_date.desc(), Invoice.id).limit(limit).offset(offset)).all())
    return invoice_responses(db, invoices)


@router.get("/{invoice_id}", response_model=InvoiceRead)
def read_invoice(invoice_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> InvoiceRead:
    invoice = get_invoice(db, user.company_id, invoice_id)
    return invoice_response(db, invoice)


@router.patch("/{invoice_id}", response_model=InvoiceRead)
def update_draft_invoice(
    invoice_id: UUID, payload: InvoiceUpdate,
    user: User = Depends(require_roles(*INVOICE_EDIT_ROLES)), db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = get_invoice(db, user.company_id, invoice_id, lock=True)
    if invoice.status != "draft":
        raise DomainError(409, "invoice_not_editable", "Only draft invoices can be edited")
    updates = payload.model_dump(exclude_unset=True)
    if not updates:
        raise DomainError(422, "empty_update", "At least one field must be provided")
    next_invoice_date = updates.get("invoice_date", invoice.invoice_date)
    next_due_date = updates.get("due_date", invoice.due_date)
    if next_due_date < next_invoice_date:
        raise DomainError(422, "invalid_due_date", "due_date must be on or after invoice_date")
    lines = updates.pop("lines", None)
    for key, value in updates.items():
        setattr(invoice, key, value)
    if lines is not None:
        invoice.lines.clear()
        db.flush()
        invoice.lines.extend(build_line(line) for line in lines)
        recalculate(invoice)
    event(db, invoice, user.id, "invoice.draft_updated", detail={"fields": list(payload.model_dump(exclude_unset=True))})
    db.commit()
    return invoice_response(db, get_invoice(db, user.company_id, invoice.id))


@router.post("/{invoice_id}/issue", response_model=InvoiceRead)
def issue_invoice(
    invoice_id: UUID, user: User = Depends(require_roles(*INVOICE_ISSUE_ROLES)), db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = get_invoice(db, user.company_id, invoice_id, lock=True)
    if invoice.status != "draft":
        raise DomainError(409, "invalid_invoice_transition", "Only draft invoices can be issued")
    if invoice.total_amount <= 0:
        raise DomainError(409, "empty_invoice", "An invoice total must be greater than zero before issuing")
    previous = invoice.status
    invoice.status = "issued"
    invoice.issued_at = datetime.now(UTC)
    event(db, invoice, user.id, "invoice.issued", previous, {"issued_at": invoice.issued_at.isoformat()})
    db.commit()
    return invoice_response(db, get_invoice(db, user.company_id, invoice.id))


@router.post("/{invoice_id}/void", response_model=InvoiceRead)
def void_invoice(
    invoice_id: UUID, payload: VoidInvoice, user: User = Depends(require_roles("owner", "admin", "billing")), db: Session = Depends(get_db),
) -> InvoiceRead:
    invoice = get_invoice(db, user.company_id, invoice_id, lock=True)
    if invoice.status not in {"draft", "issued"}:
        raise DomainError(409, "invalid_invoice_transition", "Only unpaid draft or issued invoices can be voided")
    has_payments = db.scalar(select(func.count()).select_from(Payment).where(Payment.invoice_id == invoice.id)) or 0
    if has_payments:
        raise DomainError(409, "invoice_has_payments", "An invoice with payment history cannot be voided; use a future credit/refund workflow")
    previous = invoice.status
    invoice.status = "void"
    invoice.voided_at = datetime.now(UTC)
    invoice.void_reason = payload.reason.strip()
    event(db, invoice, user.id, "invoice.voided", previous, {"reason": payload.reason})
    db.commit()
    return invoice_response(db, get_invoice(db, user.company_id, invoice.id))


@router.post("/{invoice_id}/payments", response_model=PaymentRead)
def record_payment(
    invoice_id: UUID, payload: PaymentCreate, response: Response,
    idempotency_key: str = Header(alias="Idempotency-Key", min_length=8, max_length=128),
    user: User = Depends(require_roles(*INVOICE_ISSUE_ROLES)), db: Session = Depends(get_db),
) -> Payment:
    fingerprint = payment_fingerprint(invoice_id, payload)
    existing = replay_payment(db, user.company_id, invoice_id, idempotency_key, fingerprint)
    if existing is not None:
        response.status_code = 200
        return existing
    invoice = get_invoice(db, user.company_id, invoice_id, lock=True)
    # Re-check after acquiring the invoice lock; retries for the same invoice are serialized in PostgreSQL.
    existing = replay_payment(db, user.company_id, invoice_id, idempotency_key, fingerprint)
    if existing is not None:
        response.status_code = 200
        return existing
    if invoice.status not in {"issued", "partially_paid"}:
        raise DomainError(409, "invoice_not_payable", "Only issued invoices with outstanding balances can accept payments")
    paid = db.scalar(select(func.coalesce(func.sum(Payment.amount), 0)).where(Payment.invoice_id == invoice.id)) or Decimal("0.00")
    balance = invoice.total_amount - paid
    if payload.amount > balance:
        raise DomainError(409, "overpayment", f"Payment exceeds the outstanding balance of {balance:.2f}")
    payment = Payment(
        company_id=user.company_id, invoice_id=invoice.id, amount=payload.amount,
        payment_method=payload.payment_method, reference=payload.reference,
        idempotency_key=idempotency_key, request_fingerprint=fingerprint, notes=payload.notes,
    )
    previous = invoice.status
    db.add(payment)
    db.flush()
    new_paid = paid + payload.amount
    invoice.status = "paid" if new_paid == invoice.total_amount else "partially_paid"
    event(db, invoice, user.id, "invoice.payment_recorded", previous, {
        "payment_id": str(payment.id), "amount": str(payload.amount), "payment_method": payload.payment_method,
    })
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        concurrent = replay_payment(db, user.company_id, invoice_id, idempotency_key, fingerprint)
        if concurrent is not None:
            response.status_code = 200
            return concurrent
        raise DomainError(409, "payment_conflict", "The payment conflicts with another update; reload the invoice and retry with the same Idempotency-Key") from None
    db.refresh(payment)
    return payment


@router.get("/{invoice_id}/payments", response_model=list[PaymentRead])
def list_payments(invoice_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[Payment]:
    invoice = get_invoice(db, user.company_id, invoice_id)
    return list(db.scalars(select(Payment).where(
        Payment.company_id == user.company_id, Payment.invoice_id == invoice.id
    ).order_by(Payment.received_at, Payment.id)).all())


@router.get("/{invoice_id}/events", response_model=list[InvoiceEventRead])
def list_invoice_events(invoice_id: UUID, user: User = Depends(get_current_user), db: Session = Depends(get_db)) -> list[InvoiceEvent]:
    invoice = get_invoice(db, user.company_id, invoice_id)
    return list(db.scalars(select(InvoiceEvent).where(InvoiceEvent.invoice_id == invoice.id).order_by(
        InvoiceEvent.created_at, InvoiceEvent.id
    )).all())
