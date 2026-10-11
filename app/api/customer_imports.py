import hashlib
import json
from datetime import UTC, datetime
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Response
from pydantic import ValidationError
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.api.deps import require_roles
from app.core.errors import DomainError
from app.customer_import_schemas import (
    CustomerImportDetail,
    CustomerImportPreview,
    CustomerImportPreviewRow,
    CustomerImportRead,
    CustomerImportRequest,
    CustomerImportRowInput,
    CustomerImportRowRead,
)
from app.db.session import get_db
from app.models import Company, Customer, CustomerImportJob, CustomerImportRow, User
from app.webhook_service import publish_webhook_event

router = APIRouter(prefix="/customers/imports", tags=["customer-imports"])
IMPORT_ROLES = ("owner", "admin", "manager")
MAX_ROWS = 2000


def validate_rows(raw_rows: list[dict]) -> list[CustomerImportPreviewRow]:
    seen_keys: set[tuple[str, str | None]] = set()
    results: list[CustomerImportPreviewRow] = []
    for row_number, raw in enumerate(raw_rows, start=1):
        try:
            data = CustomerImportRowInput.model_validate(raw)
            key = (data.name.casefold(), str(data.email).casefold() if data.email else None)
            if key in seen_keys:
                results.append(CustomerImportPreviewRow(
                    row_number=row_number,
                    valid=False,
                    error_code="duplicate_import_row",
                    error_message="This customer name/email combination appears more than once in the import",
                ))
                continue
            seen_keys.add(key)
            results.append(CustomerImportPreviewRow(row_number=row_number, valid=True, data=data))
        except ValidationError as exc:
            message = "; ".join(
                f"{'.'.join(str(p) for p in error['loc'])}: {error['msg']}"
                for error in exc.errors()
            )
            results.append(CustomerImportPreviewRow(
                row_number=row_number,
                valid=False,
                error_code="row_validation_failed",
                error_message=message[:2000],
            ))
    return results


def preview_from_rows(raw_rows: list[dict]) -> CustomerImportPreview:
    results = validate_rows(raw_rows)
    valid = sum(item.valid for item in results)
    return CustomerImportPreview(
        total_rows=len(results),
        valid_rows=valid,
        invalid_rows=len(results) - valid,
        rows=results,
    )


def scoped_job(db: Session, company_id: UUID, job_id: UUID) -> CustomerImportJob:
    job = db.scalar(select(CustomerImportJob).where(
        CustomerImportJob.id == job_id,
        CustomerImportJob.company_id == company_id,
    ))
    if job is None:
        raise DomainError(404, "customer_import_not_found", "Customer import not found")
    return job


def refresh_job_counts(db: Session, job: CustomerImportJob) -> None:
    rows = db.scalars(select(CustomerImportRow).where(CustomerImportRow.job_id == job.id)).all()
    job.total_rows = len(rows)
    job.imported_rows = sum(row.status == "imported" for row in rows)
    job.failed_rows = sum(row.status == "failed" for row in rows)
    pending = any(row.status == "pending" for row in rows)
    job.status = "processing" if pending else ("partial" if job.failed_rows else "completed")
    if not pending:
        job.completed_at = datetime.now(UTC)


def import_request_hash(payload: CustomerImportRequest) -> str:
    canonical = json.dumps(payload.rows, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


@router.post("/preview", response_model=CustomerImportPreview)
def preview_import(
    payload: CustomerImportRequest,
    _: User = Depends(require_roles(*IMPORT_ROLES)),
) -> CustomerImportPreview:
    return preview_from_rows(payload.rows)


@router.post("", response_model=CustomerImportRead, status_code=201)
def create_import(
    payload: CustomerImportRequest,
    response: Response,
    user: User = Depends(require_roles(*IMPORT_ROLES)),
    db: Session = Depends(get_db),
    idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
) -> CustomerImportJob:
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")

    normalized_key = idempotency_key.strip() if idempotency_key else None
    if normalized_key == "":
        normalized_key = None
    if normalized_key and len(normalized_key) > 255:
        raise DomainError(422, "invalid_idempotency_key", "Idempotency-Key must be 255 characters or fewer")

    request_hash = import_request_hash(payload)
    if normalized_key:
        existing = db.scalar(select(CustomerImportJob).where(
            CustomerImportJob.company_id == user.company_id,
            CustomerImportJob.idempotency_key == normalized_key,
        ))
        if existing is not None:
            if existing.request_hash != request_hash:
                raise DomainError(
                    409,
                    "idempotency_key_reused",
                    "The Idempotency-Key was already used with a different import request",
                )
            response.status_code = 200
            return existing

    preview = preview_from_rows(payload.rows)
    job = CustomerImportJob(
        company_id=user.company_id,
        created_by_user_id=user.id,
        total_rows=preview.total_rows,
        idempotency_key=normalized_key,
        request_hash=request_hash if normalized_key else None,
    )
    db.add(job)
    try:
        db.flush()
    except IntegrityError as exc:
        db.rollback()
        if not normalized_key:
            raise
        existing = db.scalar(select(CustomerImportJob).where(
            CustomerImportJob.company_id == user.company_id,
            CustomerImportJob.idempotency_key == normalized_key,
        ))
        if existing is None:
            raise
        if existing.request_hash != request_hash:
            raise DomainError(
                409,
                "idempotency_key_reused",
                "The Idempotency-Key was already used with a different import request",
            ) from exc
        response.status_code = 200
        return existing

    for item in preview.rows:
        row = CustomerImportRow(
            job_id=job.id,
            row_number=item.row_number,
            status="pending" if item.valid else "failed",
            payload=item.data.model_dump(mode="json") if item.data else payload.rows[item.row_number - 1],
            error_code=item.error_code,
            error_message=item.error_message,
        )
        db.add(row)
    db.flush()
    import_valid_rows(db, company, job)
    refresh_job_counts(db, job)
    db.commit()
    db.refresh(job)
    return job


def import_valid_rows(db: Session, company: Company, job: CustomerImportJob) -> None:
    rows = db.scalars(select(CustomerImportRow).where(
        CustomerImportRow.job_id == job.id,
        CustomerImportRow.status == "pending",
    ).order_by(CustomerImportRow.row_number).with_for_update()).all()
    for row in rows:
        data = CustomerImportRowInput.model_validate(row.payload)
        if data.email:
            existing = db.scalar(select(Customer.id).where(
                Customer.company_id == company.id,
                Customer.email == str(data.email).lower(),
            ))
            if existing is not None:
                row.status = "failed"
                row.error_code = "customer_email_exists"
                row.error_message = "A customer with this email already exists"
                continue
        company.customer_sequence += 1
        customer = Customer(
            company_id=company.id,
            customer_number=f"C-{company.customer_sequence:06d}",
            name=data.name,
            kind=data.kind,
            email=str(data.email).lower() if data.email else None,
            phone=data.phone,
            notes=data.notes,
        )
        db.add(customer)
        db.flush()
        row.customer_id = customer.id
        publish_webhook_event(db, company.id, "customer.created", {
            "customer_id": str(customer.id), "customer_number": customer.customer_number,
            "name": customer.name, "source": "bulk_import",
        })
        row.status = "imported"
        row.error_code = None
        row.error_message = None


@router.get("", response_model=list[CustomerImportRead])
def list_imports(
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(require_roles(*IMPORT_ROLES)),
    db: Session = Depends(get_db),
) -> list[CustomerImportJob]:
    if limit < 1 or limit > 100 or offset < 0:
        raise DomainError(422, "invalid_pagination", "limit must be 1..100 and offset must be non-negative")
    return list(db.scalars(select(CustomerImportJob).where(
        CustomerImportJob.company_id == user.company_id,
    ).order_by(CustomerImportJob.created_at.desc(), CustomerImportJob.id).limit(limit).offset(offset)).all())


@router.get("/{job_id}", response_model=CustomerImportDetail)
def get_import(
    job_id: UUID,
    user: User = Depends(require_roles(*IMPORT_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerImportJob:
    job = scoped_job(db, user.company_id, job_id)
    job.rows = list(db.scalars(select(CustomerImportRow).where(
        CustomerImportRow.job_id == job.id
    ).order_by(CustomerImportRow.row_number)).all())
    return job


@router.put("/{job_id}/rows/{row_id}", response_model=CustomerImportRowRead)
def correct_import_row(
    job_id: UUID,
    row_id: UUID,
    payload: CustomerImportRowInput,
    user: User = Depends(require_roles(*IMPORT_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerImportRow:
    job = scoped_job(db, user.company_id, job_id)
    row = db.scalar(select(CustomerImportRow).where(
        CustomerImportRow.id == row_id,
        CustomerImportRow.job_id == job.id,
    ).with_for_update())
    if row is None:
        raise DomainError(404, "customer_import_row_not_found", "Customer import row not found")
    if row.status == "imported":
        raise DomainError(409, "import_row_already_imported", "An imported row cannot be corrected")
    row.payload = payload.model_dump(mode="json")
    row.status = "pending"
    row.error_code = None
    row.error_message = None
    db.commit()
    db.refresh(row)
    return row


@router.post("/{job_id}/retry", response_model=CustomerImportRead)
def retry_failed_import_rows(
    job_id: UUID,
    user: User = Depends(require_roles(*IMPORT_ROLES)),
    db: Session = Depends(get_db),
) -> CustomerImportJob:
    company = db.scalar(select(Company).where(Company.id == user.company_id).with_for_update())
    if company is None or not company.is_active:
        raise DomainError(403, "company_inactive", "Company account is inactive")
    job = db.scalar(select(CustomerImportJob).where(
        CustomerImportJob.id == job_id,
        CustomerImportJob.company_id == user.company_id,
    ).with_for_update())
    if job is None:
        raise DomainError(404, "customer_import_not_found", "Customer import not found")
    pending = db.scalars(select(CustomerImportRow).where(
        CustomerImportRow.job_id == job.id,
        CustomerImportRow.status == "pending",
    ).with_for_update()).all()
    if not pending:
        refresh_job_counts(db, job)
        db.commit()
        db.refresh(job)
        return job
    import_valid_rows(db, company, job)
    refresh_job_counts(db, job)
    db.commit()
    db.refresh(job)
    return job
