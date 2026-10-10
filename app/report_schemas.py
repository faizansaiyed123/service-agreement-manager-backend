from datetime import date
from decimal import Decimal

from pydantic import BaseModel


class AgreementSummaryRead(BaseModel):
    as_of: date
    expiring_within_days: int
    active_count: int
    accepted_future_count: int
    expiring_count: int
    expired_by_term_count: int
    cancelled_count: int
    metric_definitions: dict[str, str]


class BillingReceivablesRead(BaseModel):
    as_of: date
    invoice_date_from: date | None
    invoice_date_to: date | None
    currency: str
    issued_invoice_count: int
    total_invoiced: Decimal
    total_paid: Decimal
    outstanding: Decimal
    overdue_invoice_count: int
    overdue_amount: Decimal
    draft_invoice_count: int
    draft_amount: Decimal


class TechnicianWorkloadRead(BaseModel):
    user_id: str
    full_name: str
    assigned_count: int
    open_count: int
    completed_count: int


class WorkOrderReportRead(BaseModel):
    as_of: date
    scheduled_from: date | None
    scheduled_to: date | None
    status_counts: dict[str, int]
    overdue_open_count: int
    technicians: list[TechnicianWorkloadRead]
