import re
from datetime import date, datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, ValidationInfo, field_validator
from .work_schemas import Pagination, PersonOut


class Input(BaseModel):
    model_config = ConfigDict(extra="forbid")

    @field_validator("*", mode="before")
    @classmethod
    def no_nulls(cls, value, info: ValidationInfo):
        if isinstance(value, str) and "\0" in value:
            raise ValueError("النص يحتوي على محرف غير صالح")
        return (
            value.strip()
            if isinstance(value, str) and info.field_name != "content"
            else value
        )


class CategoryCreate(Input):
    name: str = Field(min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    slug: str | None = Field(default=None, min_length=3, max_length=200)


class CategoryUpdate(Input):
    name: str | None = Field(default=None, min_length=3, max_length=100)
    description: str | None = Field(default=None, max_length=1000)
    slug: str | None = Field(default=None, min_length=3, max_length=200)

    @field_validator("name", "slug")
    @classmethod
    def required(cls, value):
        if value is None:
            raise ValueError("لا يمكن إفراغ الحقل")
        return value


class CategoryOut(BaseModel):
    id: str
    name: str
    description: str | None
    slug: str
    created_by: str
    created_at: datetime
    updated_at: datetime
    model_config = ConfigDict(from_attributes=True)


class ArticleCreate(Input):
    title: str = Field(min_length=5, max_length=200)
    slug: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str = Field(default="", max_length=1000)
    content: str = Field(default="", max_length=50000)
    category_id: UUID | None = None
    project_id: UUID | None = None
    language: Literal["ar", "en"] = "ar"


class ArticleUpdate(Input):
    title: str | None = Field(default=None, min_length=5, max_length=200)
    slug: str | None = Field(default=None, min_length=3, max_length=200)
    summary: str | None = Field(default=None, max_length=1000)
    content: str | None = Field(default=None, max_length=50000)
    category_id: UUID | None = None
    language: Literal["ar", "en"] | None = None

    @field_validator("title", "slug", "summary", "content", "language")
    @classmethod
    def required(cls, value):
        if value is None:
            raise ValueError("لا يمكن إفراغ الحقل")
        return value


class ArticleOut(BaseModel):
    id: str
    title: str
    slug: str
    summary: str
    content: str
    category_id: str | None
    project_id: str | None
    category: CategoryOut | None
    project_name: str | None
    author: PersonOut
    author_id: str
    status: str
    language: str
    created_at: datetime
    updated_at: datetime
    published_at: datetime | None
    archived_at: datetime | None
    can_edit: bool


class CategoryFilters(Pagination):
    q: str = Field(default="", max_length=100)
    sort: Literal["title", "newest", "oldest"] = "title"


class ArticleFilters(Pagination):
    q: str = Field(default="", max_length=200)
    category_id: UUID | None = None
    project_id: UUID | None = None
    language: Literal["ar", "en"] | None = None
    status: Literal["draft", "published", "archived", "all"] = "published"
    sort: Literal["newest", "oldest", "title"] = "newest"
    updated_from: date | None = None
    updated_to: date | None = None


class SearchFilters(Input, Pagination):
    q: str = Field(min_length=1, max_length=200)
    type: Literal["all", "article", "file"] = "all"
    category_id: UUID | None = None
    project_id: UUID | None = None
    language: Literal["ar", "en"] | None = None
    sort: Literal["relevance", "newest", "oldest", "title"] = "relevance"
    updated_from: date | None = None
    updated_to: date | None = None

    @field_validator("q")
    @classmethod
    def nonempty(cls, value):
        if not re.search(r"\w", value):
            raise ValueError("أدخل كلمة بحث واحدة على الأقل")
        return value


class SearchHit(BaseModel):
    id: str
    type: Literal["article", "file"]
    title: str
    snippet: str
    project_id: str | None
    project_name: str | None
    category_name: str | None
    updated_at: datetime
    relevance_score: float
    match_kind: str


class IndexOut(BaseModel):
    file_id: str
    indexing_status: str
    indexed_at: datetime | None
    error_code: str | None
    has_text: bool = False
    model_config = ConfigDict(from_attributes=True)
