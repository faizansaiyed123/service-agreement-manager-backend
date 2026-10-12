from calendar import monthrange
from datetime import UTC, date, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.billing_schemas import InvoiceLineInput
from app.core.errors import DomainError
from app.models import Company, Customer, Invoice, RecurringInvoiceSchedule, ServiceLocation
from app.api.billing import build_line, recalculate


def add_months(value: date, months: int) -> date:
    index = value.month - 1 + months
    year = value.year + index // 12
    month = index % 12 + 1
    day = min(value.day, monthrange(year, month)[1])
    return date(year, month, day)


def next_recurring_date(value: date, frequency: str) -> date:
    return add_months(value, {"monthly": 1, "quarterly": 3, "semi_annual": 6, "annual": 12}[frequency])


def create_scheduled_invoice(db: Session, schedule: RecurringInvoiceSchedule) -> Invoice:
    company = db.scalar(select(Company).where(Company.id == schedule.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    customer = db.scalar(select(Customer).where(
        Customer.id == schedule.customer_id,
        Customer.company_id == schedule.company_id,
        Customer.status == "active",
    ))
    if customer is None:
        raise DomainError(404, "customer_not_found", "Active recurring invoice customer not found")
    if schedule.service_location_id is not None:
        location = db.scalar(select(ServiceLocation).where(
            ServiceLocation.id == schedule.service_location_id,
            ServiceLocation.company_id == schedule.company_id,
            ServiceLocation.customer_id == schedule.customer_id,
            ServiceLocation.is_active.is_(True),
        ))
        if location is None:
            raise DomainError(404, "service_location_not_found", "Recurring invoice service location is no longer active")
    company.invoice_sequence += 1
    invoice = Invoice(
        company_id=company.id,
        customer_id=customer.id,
        service_location_id=schedule.service_location_id,
        agreement_id=schedule.agreement_id,
        invoice_number=f"INV-{company.invoice_sequence:06d}",
        status="draft",
        invoice_date=schedule.next_invoice_date,
        due_date=schedule.next_invoice_date.fromordinal(schedule.next_invoice_date.toordinal() + schedule.due_days),
        currency=schedule.currency,
        notes=schedule.notes,
        discount_percent=schedule.discount_percent,
        tax_percent=schedule.tax_percent,
    )
    db.add(invoice)
    db.flush()
    for raw in schedule.line_templates:
        invoice.lines.append(build_line(InvoiceLineInput.model_validate(raw)))
    recalculate(invoice)
    db.flush()
    return invoice
