import hashlib
import logging
import os
from threading import BoundedSemaphore
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import select
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session, joinedload

from .config import get_settings
from .file_schemas import FileOut
from .file_storage import CHUNK_SIZE, PrivateStorage, storage_unavailable
from .file_validation import validate_content, validate_name
from .models import FileSearchIndex, ProjectFile, Role, utcnow
from .work_repository import paginate
from .work_services import get_project

logger = logging.getLogger("workspace.storage")
UPLOAD_SLOTS = BoundedSemaphore(2)


def file_query():
    return select(ProjectFile).options(joinedload(ProjectFile.uploader))


def get_file(db, file_id, user, *, write=False):
    row = db.get(ProjectFile, str(file_id), populate_existing=True)
    if not row or row.deleted_at is not None:
        raise HTTPException(404, "الملف غير موجود أو غير متاح")
    project = get_project(db, row.project_id, user, write=write)
    if write:
        db.refresh(row)  # Re-read after the project lock; another delete may have won.
        if row.deleted_at is not None:
            raise HTTPException(404, "الملف غير موجود أو غير متاح")
    return row, project


def metadata(db, file_id, user):
    get_file(db, file_id, user)
    return FileOut.model_validate(db.scalar(file_query().where(ProjectFile.id == str(file_id))))


def upload_file(db, user, project_id, upload):
    get_project(db, project_id, user)  # Rechecked under a lock before commit.
    # python-multipart normalizes legacy Windows paths to a basename. Inspect
    # the preserved raw part header too, so traversal attempts are rejected.
    if "\\" in upload.headers.get("content-disposition", ""):
        raise HTTPException(400, "اسم الملف لا يجوز أن يحتوي على مسار")
    name, extension = validate_name(upload.filename)
    if not UPLOAD_SLOTS.acquire(blocking=False):
        raise HTTPException(429, "تجري معالجة ملفات أخرى. أعد المحاولة بعد قليل.", headers={"Retry-After": "2"})
    storage = PrivateStorage()
    final = None
    row = None
    committing = False
    try:
        with storage.temporary() as (temporary, stream):
            size = 0
            digest = hashlib.sha256()
            while chunk := upload.file.read(CHUNK_SIZE):
                size += len(chunk)
                if size > get_settings().max_upload_bytes:
                    raise HTTPException(413, "حجم الملف أكبر من الحد المسموح (10MB كحد أقصى).")
                digest.update(chunk)
                stream.write(chunk)
            if size == 0:
                raise HTTPException(400, "لا يمكن رفع ملف فارغ")
            stream.flush(); os.fsync(stream.fileno()); stream.close()
            mime = validate_content(temporary, extension)
            db.refresh(user)
            if not user.is_active:
                raise HTTPException(401, "الحساب معطّل")
            project = get_project(db, project_id, user, write=True)
            key = uuid4().hex
            final = storage.promote(temporary, key)
            row = ProjectFile(id=str(uuid4()), project_id=project.id, uploaded_by=user.id, original_name=name,
                              storage_key=key, mime_type=mime, extension=extension,
                              size_bytes=size, checksum=digest.hexdigest())
            db.add(row)
            db.flush()
            if db.get_bind().dialect.name == 'sqlite':
                db.add(FileSearchIndex(file_id=row.id,indexing_status='pending'))
            committing = True
            db.commit()
            final = None  # A committed object must never be removed by response serialization errors.
            return metadata(db, row.id, user)
    except BaseException as error:
        if final is not None:
            # A connection can fail AFTER PostgreSQL commits. If its outcome is
            # unknown, retain the final object for the read-only audit to flag.
            remove = not committing
            row_id = row.id if row is not None else None
            try:
                db.rollback()
                if committing:
                    with Session(db.get_bind()) as check:
                        remove = check.get(ProjectFile, row_id) is None
            except SQLAlchemyError:
                logger.error("upload_commit_outcome_unknown file_id=%s", row_id)
            if remove:
                storage.cleanup(final)
        if isinstance(error, OSError):
            raise storage_unavailable(error) from None
        raise
    finally:
        UPLOAD_SLOTS.release()


def list_files(db, project_id, user, filters):
    project = get_project(db, project_id, user)
    statement = file_query().where(ProjectFile.project_id == project.id, ProjectFile.deleted_at.is_(None))
    if filters.q:
        statement = statement.where(ProjectFile.original_name.icontains(filters.q.strip(), autoescape=True))
    if filters.type:
        statement = statement.where(ProjectFile.extension.in_(["jpg", "jpeg"]) if filters.type in {"jpg", "jpeg"} else ProjectFile.extension == filters.type)
    if filters.uploaded_by:
        statement = statement.where(ProjectFile.uploaded_by == str(filters.uploaded_by))
    column = getattr(ProjectFile, filters.sort_by)
    ordering = column.asc() if filters.sort_order == "asc" else column.desc()
    return paginate(db, statement.order_by(ordering, ProjectFile.id.asc()), filters, FileOut.model_validate)


def delete_file(db, file_id, user):
    row, project = get_file(db, file_id, user, write=True)
    if user.role == Role.EMPLOYEE and row.uploaded_by != user.id:
        raise HTTPException(403, "يمكنك حذف الملفات التي رفعتها بنفسك فقط")
    row.deleted_at = utcnow()
    db.commit()


def open_download(db, file_id, user):
    row, _ = get_file(db, file_id, user)
    storage = PrivateStorage()
    try:
        path = storage.path(row.storage_key)
        stream = path.open("rb")
        if os.fstat(stream.fileno()).st_size != row.size_bytes:
            stream.close()
            raise HTTPException(409, "تعذر تنزيل الملف. يرجى إبلاغ مسؤول النظام.")
        return stream, row.original_name, row.mime_type, row.size_bytes
    except FileNotFoundError:
        logger.error("stored_file_missing file_id=%s", row.id)
        raise HTTPException(404, "الملف غير متاح حاليًا. يرجى إبلاغ مسؤول النظام.") from None
    except OSError as error:
        raise storage_unavailable(error) from None
