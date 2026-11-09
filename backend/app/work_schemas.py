from datetime import date, datetime
from typing import Generic, Literal, TypeVar
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .models import Priority, ProjectStatus, Role, TaskStatus


class StrictInput(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)


class ProjectCreate(StrictInput):
    name: str = Field(min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    manager_id: UUID
    status: ProjectStatus = ProjectStatus.PLANNING
    start_date: date | None = None
    end_date: date | None = None

    @model_validator(mode="after")
    def dates(self):
        if self.start_date and self.end_date and self.end_date < self.start_date:
            raise ValueError("تاريخ النهاية يجب أن يساوي تاريخ البداية أو يليه")
        return self


class ProjectUpdate(StrictInput):
    name: str | None = Field(default=None, min_length=3, max_length=150)
    description: str | None = Field(default=None, max_length=10000)
    manager_id: UUID | None = None
    status: ProjectStatus | None = None
    start_date: date | None = None
    end_date: date | None = None

    @field_validator("name", "manager_id", "status")
    @classmethod
    def non_null(cls, value):
        if value is None:
            raise ValueError("لا يمكن ترك هذا الحقل فارغًا")
        return value


class PersonOut(BaseModel):
    id: str
    name: str
    email: str
    role: Role
    is_active: bool
    model_config = ConfigDict(from_attributes=True)


class ProjectOut(BaseModel):
    id: str
    name: str
    description: str | None
    manager_id: str
    created_by: str
    manager: PersonOut
    status: ProjectStatus
    start_date: date | None
    end_date: date | None
    is_archived: bool
    archived_at: datetime | None
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class MemberCreate(StrictInput):
    user_id: UUID


class MemberOut(BaseModel):
    id: str
    project_id: str
    user_id: str
    joined_at: datetime
    user: PersonOut
    model_config = ConfigDict(from_attributes=True)


class TaskCreate(StrictInput):
    title: str = Field(min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assigned_to: UUID
    status: TaskStatus = TaskStatus.TODO
    priority: Priority = Priority.MEDIUM
    due_date: date | None = None


class TaskUpdate(StrictInput):
    title: str | None = Field(default=None, min_length=3, max_length=200)
    description: str | None = Field(default=None, max_length=10000)
    assigned_to: UUID | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_date: date | None = None

    @field_validator("title", "assigned_to", "status", "priority")
    @classmethod
    def non_null(cls, value):
        if value is None:
            raise ValueError("لا يمكن ترك هذا الحقل فارغًا")
        return value


class TaskStatusUpdate(StrictInput):
    status: TaskStatus


class TaskOut(BaseModel):
    id: str
    project_id: str
    project_name: str
    project_archived: bool
    title: str
    description: str | None
    assigned_to: str
    assignee: PersonOut
    created_by: str
    creator: PersonOut
    status: TaskStatus
    priority: Priority
    due_date: date | None
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None
    is_overdue: bool


Item = TypeVar("Item")


class Page(BaseModel, Generic[Item]):
    items: list[Item]
    page: int
    page_size: int
    total: int
    total_pages: int


class Pagination(BaseModel):
    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=100)


class ProjectFilters(Pagination):
    q: str | None = Field(default=None, max_length=150)
    status: ProjectStatus | None = None
    manager_id: UUID | None = None
    created_from: date | None = None
    created_to: date | None = None
    archived: bool = False
    sort_by: Literal["created_at", "name", "start_date", "end_date"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"


class TaskFilters(Pagination):
    q: str | None = Field(default=None, max_length=200)
    project_id: UUID | None = None
    assigned_to: UUID | None = None
    status: TaskStatus | None = None
    priority: Priority | None = None
    due_from: date | None = None
    due_to: date | None = None
    overdue: bool | None = None
    archived: bool = False
    sort_by: Literal["created_at", "due_date", "priority"] = "created_at"
    sort_order: Literal["asc", "desc"] = "desc"
