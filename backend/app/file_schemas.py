from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from .work_schemas import Pagination, PersonOut


class FileOut(BaseModel):
    id: str
    project_id: str
    uploaded_by: str
    uploader: PersonOut
    original_name: str
    mime_type: str
    extension: str
    size_bytes: int
    checksum: str
    created_at: datetime
    model_config = ConfigDict(from_attributes=True)


class FileFilters(Pagination):
    q: str | None = Field(default=None, max_length=255)
    type: Literal["pdf", "png", "jpg", "jpeg", "docx"] | None = None
    uploaded_by: UUID | None = None
    sort_by: Literal["original_name", "size_bytes", "created_at"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
