from datetime import UTC, datetime
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import APIRouter, Depends, File, Form, UploadFile
from fastapi.responses import FileResponse
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_roles
from app.attachment_schemas import AttachmentEntityType, AttachmentRead, AttachmentUpdate
from app.core.config import get_settings
from app.core.errors import DomainError
from app.core.storage import LocalStorage, StorageLimitExceeded
from app.db.session import get_db
from app.models import (
    Agreement,
    Attachment,
    Customer,
    Equipment,
    Invoice,
    ServiceLocation,
    User,
    WorkOrder,
)

router = APIRouter(prefix="/attachments", tags=["attachments"])

ALL_ROLES = ("owner", "admin", "manager", "technician", "billing", "staff")
DELETE_ROLES = ("owner", "admin", "manager")

ENTITY_MODELS = {
    "customer": Customer,
    "service_location": ServiceLocation,
    "equipment": Equipment,
    "agreement": Agreement,
    "work_order": WorkOrder,
    "invoice": Invoice,
}


def storage() -> LocalStorage:
    settings = get_settings()
    if settings.storage_backend.lower() != "local":
        raise DomainError(503, "storage_backend_unavailable", "Configured attachment storage backend is unavailable")
    return LocalStorage(settings.storage_root, settings.storage_max_file_bytes)


def scoped_attachment(db: Session, company_id: UUID, attachment_id: UUID) -> Attachment:
    attachment = db.scalar(select(Attachment).where(
        Attachment.id == attachment_id,
        Attachment.company_id == company_id,
        Attachment.status == "active",
    ))
    if attachment is None:
        raise DomainError(404, "attachment_not_found", "Attachment not found")
    return attachment


def ensure_entity(db: Session, company_id: UUID, entity_type: AttachmentEntityType, entity_id: UUID) -> None:
    model = ENTITY_MODELS[entity_type]
    exists = db.scalar(select(model.id).where(
        model.id == entity_id,
        model.company_id == company_id,
    ))
    if exists is None:
        raise DomainError(404, "attachment_entity_not_found", "Attachment target was not found")


@router.post(
    "/{entity_type}/{entity_id}",
    response_model=AttachmentRead,
    status_code=201,
)
def upload_attachment(
    entity_type: AttachmentEntityType,
    entity_id: UUID,
    file: UploadFile = File(...),
    description: str | None = Form(default=None),
    user: User = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> Attachment:
    ensure_entity(db, user.company_id, entity_type, entity_id)

    filename = Path(file.filename or "").name.strip()
    if not filename or filename in {".", ".."}:
        raise DomainError(422, "invalid_attachment_filename", "A valid attachment filename is required")
    if "\x00" in filename:
        raise DomainError(422, "invalid_attachment_filename", "The attachment filename contains an invalid character")
    if len(filename) > 255:
        raise DomainError(422, "invalid_attachment_filename", "Attachment filename must be 255 characters or fewer")

    description = description.strip() if description else None
    if description and len(description) > 4000:
        raise DomainError(422, "invalid_attachment_description", "Attachment description must be 4000 characters or fewer")

    content_type = (file.content_type or "application/octet-stream").strip() or "application/octet-stream"
    if len(content_type) > 255:
        raise DomainError(422, "invalid_attachment_content_type", "Attachment content type is too long")

    attachment_id = uuid4()
    storage_key = f"{user.company_id}/{entity_type}/{entity_id}/{attachment_id}"
    backend = storage()

    try:
        size_bytes, checksum = backend.save_stream(file.file, storage_key)
        attachment = Attachment(
            id=attachment_id,
            company_id=user.company_id,
            uploaded_by_user_id=user.id,
            entity_type=entity_type,
            entity_id=entity_id,
            original_filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            sha256=checksum,
            storage_key=storage_key,
            description=description,
        )
        db.add(attachment)
        db.commit()
        db.refresh(attachment)
        return attachment
    except StorageLimitExceeded as exc:
        db.rollback()
        backend.delete(storage_key)
        raise DomainError(413, "attachment_too_large", str(exc)) from exc
    except Exception:
        db.rollback()
        backend.delete(storage_key)
        raise


@router.get("", response_model=list[AttachmentRead])
def list_attachments(
    entity_type: AttachmentEntityType | None = None,
    entity_id: UUID | None = None,
    limit: int = 50,
    offset: int = 0,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> list[Attachment]:
    if limit < 1 or limit > 100 or offset < 0:
        raise DomainError(422, "invalid_pagination", "limit must be 1..100 and offset must be non-negative")
    if entity_id is not None and entity_type is None:
        raise DomainError(422, "invalid_attachment_filter", "entity_type is required when entity_id is provided")

    query = select(Attachment).where(
        Attachment.company_id == user.company_id,
        Attachment.status == "active",
    )
    if entity_type:
        query = query.where(Attachment.entity_type == entity_type)
    if entity_id:
        query = query.where(Attachment.entity_id == entity_id)

    return list(db.scalars(
        query.order_by(Attachment.created_at.desc(), Attachment.id).limit(limit).offset(offset)
    ).all())


@router.get("/{attachment_id}", response_model=AttachmentRead)
def get_attachment(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Attachment:
    return scoped_attachment(db, user.company_id, attachment_id)


@router.get("/{attachment_id}/download", response_class=FileResponse)
def download_attachment(
    attachment_id: UUID,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> FileResponse:
    attachment = scoped_attachment(db, user.company_id, attachment_id)
    backend = storage()
    path = backend.path_for(attachment.storage_key)
    if not path.is_file():
        raise DomainError(410, "attachment_storage_missing", "Attachment metadata exists but stored content is missing")
    return FileResponse(
        path=path,
        media_type=attachment.content_type,
        filename=attachment.original_filename,
        headers={"X-Attachment-SHA256": attachment.sha256},
    )


@router.patch("/{attachment_id}", response_model=AttachmentRead)
def update_attachment(
    attachment_id: UUID,
    payload: AttachmentUpdate,
    user: User = Depends(require_roles(*ALL_ROLES)),
    db: Session = Depends(get_db),
) -> Attachment:
    attachment = scoped_attachment(db, user.company_id, attachment_id)
    attachment.description = payload.description.strip() if payload.description else None
    db.commit()
    db.refresh(attachment)
    return attachment


@router.delete("/{attachment_id}", response_model=AttachmentRead)
def delete_attachment(
    attachment_id: UUID,
    user: User = Depends(require_roles(*DELETE_ROLES)),
    db: Session = Depends(get_db),
) -> Attachment:
    attachment = scoped_attachment(db, user.company_id, attachment_id)
    attachment.status = "deleted"
    attachment.deleted_at = datetime.now(UTC)
    backend = storage()
    db.commit()
    try:
        backend.delete(attachment.storage_key)
    except OSError:
        pass
    return attachment
