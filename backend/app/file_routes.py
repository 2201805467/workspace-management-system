from typing import Annotated
from urllib.parse import quote
from uuid import UUID

from fastapi import APIRouter, HTTPException, Request
from fastapi import Query
from fastapi.responses import StreamingResponse
from starlette.background import BackgroundTask
from starlette.concurrency import run_in_threadpool
from starlette.datastructures import UploadFile
from starlette.formparsers import MultiPartException
from starlette.exceptions import HTTPException as StarletteHTTPException
from starlette.requests import ClientDisconnect

from . import file_services as service
from .config import get_settings
from .file_schemas import FileFilters, FileOut
from .file_storage import CHUNK_SIZE, logger, storage_unavailable
from .file_validation import MIME_TYPES
from .security import CurrentUser, Db
from .work_schemas import Page
from .work_schemas import PersonOut
from .models import ProjectFile, User
from .models import FileSearchIndex
from .knowledge_schemas import IndexOut
from sqlalchemy import select
from .work_services import get_project

router = APIRouter(prefix="/api", tags=["Files"])
TOO_LARGE = "workspace-upload-body-limit"


@router.get("/files/policy")
def policy(user: CurrentUser):
    return {
        "max_size_bytes": get_settings().max_upload_bytes,
        "allowed_types": MIME_TYPES,
    }


@router.post(
    "/projects/{project_id}/files",
    response_model=FileOut,
    status_code=201,
    openapi_extra={
        "requestBody": {
            "required": True,
            "content": {
                "multipart/form-data": {
                    "schema": {
                        "type": "object",
                        "required": ["file"],
                        "properties": {"file": {"type": "string", "format": "binary"}},
                    }
                }
            },
        }
    },
)
async def upload(project_id: UUID, request: Request, user: CurrentUser, db: Db):
    # Deliberately parse manually: declarative File(...) would parse/spool the
    # body before dependencies get a chance to authorize project access.
    project = await run_in_threadpool(get_project, db, project_id, user)
    if project.is_archived:
        raise HTTPException(409, "المشروع مؤرشف ومتاح للقراءة فقط")
    if (
        request.headers.get("content-type", "").split(";", 1)[0].strip().lower()
        != "multipart/form-data"
    ):
        raise HTTPException(415, "أرسل الملف باستخدام multipart/form-data")
    limit = get_settings().max_upload_bytes + 64 * 1024
    try:
        if (
            "content-length" in request.headers
            and int(request.headers["content-length"]) > limit
        ):
            raise HTTPException(413, "حجم طلب الرفع أكبر من الحد المسموح")
    except ValueError:
        raise HTTPException(400, "حجم الطلب غير صالح") from None
    received = 0

    async def limited_receive():
        nonlocal received
        message = await request.receive()
        if message["type"] == "http.request":
            received += len(message.get("body", b""))
            if received > limit:
                # Starlette's parser catches this type and closes every spooled
                # temporary file, including on an oversized chunked request.
                raise MultiPartException(TOO_LARGE)
        return message

    bounded = Request(request.scope, receive=limited_receive)
    try:
        async with bounded.form(
            max_files=1, max_fields=0, max_part_size=64 * 1024
        ) as form:
            upload = form.get("file")
            if len(form.multi_items()) != 1 or not isinstance(upload, UploadFile):
                raise HTTPException(422, "أرسل ملفًا واحدًا في الحقل file")
            return await run_in_threadpool(
                service.upload_file, db, user, project_id, upload
            )
    except StarletteHTTPException as error:
        if received > limit or error.detail == TOO_LARGE:
            raise HTTPException(413, "حجم طلب الرفع أكبر من الحد المسموح") from None
        if error.status_code == 400:
            raise HTTPException(400, "طلب رفع غير صالح أو غير مكتمل") from None
        raise
    except ClientDisconnect:
        raise HTTPException(400, "انقطع الاتصال قبل اكتمال رفع الملف") from None
    except OSError as error:
        raise storage_unavailable(error) from None


@router.get("/projects/{project_id}/files", response_model=Page[FileOut])
def files(
    project_id: UUID,
    filters: Annotated[FileFilters, Query()],
    user: CurrentUser,
    db: Db,
):
    return service.list_files(db, project_id, user, filters)


@router.get("/projects/{project_id}/file-uploaders", response_model=list[PersonOut])
def uploaders(project_id: UUID, user: CurrentUser, db: Db):
    get_project(db, project_id, user)
    return db.scalars(
        select(User)
        .join(ProjectFile, ProjectFile.uploaded_by == User.id)
        .where(
            ProjectFile.project_id == str(project_id), ProjectFile.deleted_at.is_(None)
        )
        .distinct()
        .order_by(User.name, User.id)
    ).all()


@router.get("/files/{file_id}", response_model=FileOut)
def metadata(file_id: UUID, user: CurrentUser, db: Db):
    return service.metadata(db, file_id, user)


@router.get("/files/{file_id}/download")
def download(file_id: UUID, user: CurrentUser, db: Db):
    stream, name, mime, size = service.open_download(db, file_id, user)

    def chunks():
        try:
            with stream:
                while chunk := stream.read(CHUNK_SIZE):
                    yield chunk
        except OSError as error:
            logger.error("download_stream_failed type=%s", type(error).__name__)
            # Headers may already be sent. Stop the stream; Content-Length lets
            # the client detect truncation without exposing an internal error.

    return StreamingResponse(
        chunks(),
        media_type=mime,
        background=BackgroundTask(stream.close),
        headers={
            "Content-Length": str(size),
            "X-Content-Type-Options": "nosniff",
            "Cache-Control": "no-store",
            "Content-Security-Policy": "sandbox; default-src 'none'",
            "Content-Disposition": "attachment; filename*=UTF-8''"
            + quote(name, safe=""),
        },
    )


@router.get("/files/{file_id}/index", response_model=IndexOut)
def index_status(file_id: UUID, user: CurrentUser, db: Db):
    service.get_file(db, file_id, user)
    row = db.scalar(
        select(FileSearchIndex).where(FileSearchIndex.file_id == str(file_id))
    )
    if row is None:
        return dict(
            file_id=str(file_id),
            indexing_status="pending",
            indexed_at=None,
            error_code=None,
        )
    return dict(
        file_id=row.file_id,
        indexing_status=row.indexing_status,
        indexed_at=row.indexed_at,
        error_code=row.error_code,
        has_text=bool(row.extracted_text),
    )


@router.post("/files/{file_id}/reindex", response_model=IndexOut)
def reindex(file_id: UUID, user: CurrentUser, db: Db):
    from fastapi import HTTPException
    from .models import Role, utcnow

    if user.role != Role.ADMIN:
        raise HTTPException(403, "إعادة الفهرسة متاحة للمسؤول فقط")
    row, _ = service.get_file(db, file_id, user)
    job = db.scalar(
        select(FileSearchIndex)
        .where(FileSearchIndex.file_id == row.id)
        .with_for_update()
    )
    if job is None:
        job = FileSearchIndex(file_id=row.id)
        db.add(job)
    job.indexing_status = "pending"
    job.extracted_text = ""
    job.error_code = None
    job.lease_token = None
    job.updated_at = utcnow()
    db.commit()
    db.refresh(job)
    return job


@router.delete("/files/{file_id}", status_code=204)
def delete(file_id: UUID, user: CurrentUser, db: Db):
    service.delete_file(db, file_id, user)
