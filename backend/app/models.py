from datetime import date, datetime, timezone
from enum import Enum
from uuid import uuid4

from sqlalchemy import Boolean, CheckConstraint, Date, DateTime, Enum as SqlEnum, ForeignKey, ForeignKeyConstraint, Index, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .db import Base


def utcnow():
    return datetime.now(timezone.utc)


class Role(str, Enum):
    ADMIN = "Admin"
    MANAGER = "Manager"
    EMPLOYEE = "Employee"


class User(Base):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(100))
    email: Mapped[str] = mapped_column(String(254), unique=True, index=True)
    password_hash: Mapped[str] = mapped_column(String(512))
    role: Mapped[Role] = mapped_column(SqlEnum(Role, native_enum=False, create_constraint=True))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)


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
    return SqlEnum(enum, name=name, native_enum=False, create_constraint=True,
                   values_callable=lambda values: [item.value for item in values])


class Project(Base):
    __tablename__ = "projects"
    __table_args__ = (
        CheckConstraint("end_date IS NULL OR start_date IS NULL OR end_date >= start_date", name="ck_project_dates"),
        CheckConstraint("length(trim(name)) BETWEEN 3 AND 150", name="ck_project_name"),
        CheckConstraint("(is_archived AND archived_at IS NOT NULL) OR (NOT is_archived AND archived_at IS NULL)", name="ck_project_archive"),
        Index("ix_projects_manager_archived_created", "manager_id", "is_archived", "created_at", "id"),
        Index("ix_projects_archived_created", "is_archived", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    name: Mapped[str] = mapped_column(String(150))
    description: Mapped[str | None] = mapped_column(Text)
    manager_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[ProjectStatus] = mapped_column(value_enum(ProjectStatus, "project_status"), default=ProjectStatus.PLANNING)
    start_date: Mapped[date | None] = mapped_column(Date)
    end_date: Mapped[date | None] = mapped_column(Date)
    is_archived: Mapped[bool] = mapped_column(Boolean, default=False)
    archived_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    manager: Mapped[User] = relationship(foreign_keys=[manager_id])


class ProjectMember(Base):
    __tablename__ = "project_members"
    __table_args__ = (
        UniqueConstraint("project_id", "user_id", name="uq_project_member"),
        Index("ix_project_members_user_project", "user_id", "project_id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    user_id: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    joined_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    user: Mapped[User] = relationship()


class Task(Base):
    __tablename__ = "tasks"
    __table_args__ = (
        ForeignKeyConstraint(["project_id", "assigned_to"], ["project_members.project_id", "project_members.user_id"], ondelete="RESTRICT", name="fk_task_membership"),
        CheckConstraint("length(trim(title)) BETWEEN 3 AND 200", name="ck_task_title"),
        CheckConstraint("(status = 'done' AND completed_at IS NOT NULL) OR (status <> 'done' AND completed_at IS NULL)", name="ck_task_completion"),
        Index("ix_tasks_project_status_due", "project_id", "status", "due_date", "id"),
        Index("ix_tasks_assignee_created", "assigned_to", "created_at", "id"),
        Index("ix_tasks_project_created", "project_id", "created_at", "id"),
    )
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid4()))
    project_id: Mapped[str] = mapped_column(ForeignKey("projects.id", ondelete="RESTRICT"))
    title: Mapped[str] = mapped_column(String(200))
    description: Mapped[str | None] = mapped_column(Text)
    assigned_to: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    created_by: Mapped[str] = mapped_column(ForeignKey("users.id", ondelete="RESTRICT"))
    status: Mapped[TaskStatus] = mapped_column(value_enum(TaskStatus, "task_status"), default=TaskStatus.TODO)
    priority: Mapped[Priority] = mapped_column(value_enum(Priority, "task_priority"), default=Priority.MEDIUM)
    due_date: Mapped[date | None] = mapped_column(Date)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    assignee: Mapped[User] = relationship(foreign_keys=[assigned_to])
    creator: Mapped[User] = relationship(foreign_keys=[created_by])
    project: Mapped[Project] = relationship(foreign_keys=[project_id])
