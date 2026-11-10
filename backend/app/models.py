from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    Date,
    DateTime,
    Enum as SqlEnum,
    ForeignKey,
    ForeignKeyConstraint,
    Index,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.dialects.postgresql import TSVECTOR

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[Role] = mapped_column(
        SqlEnum(Role, native_enum=False, create_constraint=True)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )


class AccessSession(Base):
    __tablename__ = "access_sessions"

    token_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id"), index=True)
    expires_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), index=True)


class ProjectStatus(str, Enum):
    PLANNING = "Planning"
    ACTIVE = "Active"
    ON_HOLD = "On Hold"
    COMPLETED = "Completed"
    CANCELLED = "Cancelled"


class TaskStatus(str, Enum):
    TODO = "todo"
    IN_PROGRESS = "in_progress"
    BLOCKED = "blocked"
    DONE = "done"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


def value_enum(enum, name):
    return SqlEnum(
        enum,
        name=name,
        native_enum=False,
        create_constraint=True,
        values_callable=lambda values: [item.value for item in values],
    )


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint(
            "end_date IS NULL OR start_date IS NULL OR end_date >= start_date",
            name="ck_project_dates",
        ),
        CheckConstraint("length(trim(name)) BETWEEN 3 AND 150", name="ck_project_name"),
        CheckConstraint(
            "(is_archived AND archived_at IS NOT NULL) OR (NOT is_archived AND archived_at IS NULL)",
            name="ck_project_archive",
        ),
        Index(
            "ix_projects_manager_archived_created",
            "manager_id",
            "is_archived",
            "created_at",
            "id",
        ),
        Index("ix_projects_archived_created", "is_archived", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[ProjectStatus] = mapped_column(
        value_enum(ProjectStatus, "project_status"), default=ProjectStatus.PLANNING
    )
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    manager: Mapped[User] = relationship(foreign_keys=[manager_id])


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        Index("ix_project_members_user_project", "user_id", "project_id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(
            ["project_id", "assigned_to"],
            ["project_members.project_id", "project_members.user_id"],
            ondelete="RESTRICT",
            name="fk_task_membership",
        ),
        CheckConstraint("length(trim(title)) BETWEEN 3 AND 200", name="ck_task_title"),
        CheckConstraint(
            "(status = 'done' AND completed_at IS NOT NULL) OR (status <> 'done' AND completed_at IS NULL)",
            name="ck_task_completion",
        ),
        Index("ix_tasks_project_status_due", "project_id", "status", "due_date", "id"),
        Index("ix_tasks_assignee_created", "assigned_to", "created_at", "id"),
        Index("ix_tasks_project_created", "project_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[TaskStatus] = mapped_column(
        value_enum(TaskStatus, "task_status"), default=TaskStatus.TODO
    )
    priority: Mapped[Priority] = mapped_column(
        value_enum(Priority, "task_priority"), default=Priority.MEDIUM
    )
    due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee: Mapped[User] = relationship(foreign_keys=[assigned_to])
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    project: Mapped[Project] = relationship(foreign_keys=[project_id])


class ProjectFile(Base):
    __tablename__ = "files"
    __table_args__ = (
        CheckConstraint(
            "size_bytes > 0 AND size_bytes <= 10485760", name="ck_files_size"
        ),
        CheckConstraint(
            "extension IN ('pdf', 'png', 'jpg', 'jpeg', 'docx')",
            name="ck_files_extension",
        ),
        CheckConstraint("length(checksum) = 64", name="ck_files_checksum"),
        Index(
            "ix_files_project_deleted_created",
            "project_id",
            "deleted_at",
            "created_at",
            "id",
        ),
        Index("ix_files_uploader_created", "uploaded_by", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    project_id: Mapped[str] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    uploaded_by: Mapped[str] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT")
    )
    original_name: Mapped[str] = mapped_column(String(255))
    storage_key: Mapped[str] = mapped_column(String(64), unique=True)
    mime_type: Mapped[str] = mapped_column(String(100))
    extension: Mapped[str] = mapped_column(String(5))
    size_bytes: Mapped[int] = mapped_column()
    checksum: Mapped[str] = mapped_column(String(64))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    deleted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    uploader: Mapped[User] = relationship(foreign_keys=[uploaded_by])


class KnowledgeCategory(Base):
    __tablename__ = "knowledge_categories"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    name: Mapped[str] = mapped_column(String(100))
    description: Mapped[str | None] = mapped_column(String(1000))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )


class KnowledgeArticle(Base):
    __tablename__ = "knowledge_articles"
    __table_args__ = (
        CheckConstraint(
            "status IN ('draft','published','archived')", name="ck_article_status"
        ),
        CheckConstraint("language IN ('ar','en')", name="ck_article_language"),
        CheckConstraint(
            "length(trim(title)) BETWEEN 5 AND 200 AND length(content) <= 50000",
            name="ck_article_text",
        ),
        CheckConstraint(
            "status <> 'published' OR (published_at IS NOT NULL AND length(trim(content)) > 0)",
            name="ck_article_publication",
        ),
        CheckConstraint(
            "(status = 'archived' AND archived_at IS NOT NULL) OR (status <> 'archived' AND archived_at IS NULL)",
            name="ck_article_archive",
        ),
        Index(
            "ix_articles_scope_status_updated",
            "project_id",
            "status",
            "updated_at",
            "id",
        ),
        Index("ix_articles_category", "category_id"),
        Index("ix_articles_published", "published_at"),
        Index("ix_articles_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_articles_title_trgm",
            "search_title",
            postgresql_using="gin",
            postgresql_ops={"search_title": "gin_trgm_ops"},
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    title: Mapped[str] = mapped_column(String(200))
    slug: Mapped[str] = mapped_column(String(200), unique=True)
    summary: Mapped[str] = mapped_column(String(1000), default="")
    content: Mapped[str] = mapped_column(Text, default="")
    category_id: Mapped[str | None] = mapped_column(
        ForeignKey("knowledge_categories.id", ondelete="RESTRICT")
    )
    project_id: Mapped[str | None] = mapped_column(
        ForeignKey("projects.id", ondelete="RESTRICT")
    )
    author_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[str] = mapped_column(String(12), default="draft")
    language: Mapped[str] = mapped_column(String(2), default="ar")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite")
    )
    search_title: Mapped[str] = mapped_column(Text, default="")
    category: Mapped[KnowledgeCategory | None] = relationship()
    author: Mapped[User] = relationship()
    project: Mapped[Project | None] = relationship()


class FileSearchIndex(Base):
    __tablename__ = "file_search_index"
    __table_args__ = (
        CheckConstraint(
            "indexing_status IN ('pending','processing','ready','failed')",
            name="ck_index_status",
        ),
        Index("ix_file_index_queue", "indexing_status", "updated_at"),
        Index("ix_file_index_search", "search_vector", postgresql_using="gin"),
        Index(
            "ix_file_index_title_trgm",
            "search_title",
            postgresql_using="gin",
            postgresql_ops={"search_title": "gin_trgm_ops"},
        ),
    )
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    file_id: Mapped[str] = mapped_column(
        ForeignKey("files.id", ondelete="CASCADE"), unique=True
    )
    extracted_text: Mapped[str] = mapped_column(Text, default="")
    indexing_status: Mapped[str] = mapped_column(String(12), default="pending")
    indexed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_code: Mapped[str | None] = mapped_column(String(40))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow
    )
    lease_token: Mapped[str | None] = mapped_column(String(36))
    search_title: Mapped[str] = mapped_column(Text, default="")
    search_vector: Mapped[str | None] = mapped_column(
        TSVECTOR().with_variant(Text(), "sqlite")
    )


class ActivityLog(Base):
    __tablename__ = "activity_log"
    id: Mapped[str] = mapped_column(
        String(36), primary_key=True, default=lambda: str(uuid4())
    )
    actor_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    article_id: Mapped[str] = mapped_column(
        ForeignKey("knowledge_articles.id", ondelete="CASCADE"), index=True
    )
    action: Mapped[str] = mapped_column(String(40))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow
    )
