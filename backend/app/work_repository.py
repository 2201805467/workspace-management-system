"""SQL queries and transaction boundaries for project/task operations."""
from math import ceil

from fastapi import HTTPException
from sqlalchemy import case, exists, func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import joinedload

from .models import Priority, Project, ProjectMember, Role, Task, User


def visible_projects(user: User):
    if user.role == Role.ADMIN:
        return True
    if user.role == Role.MANAGER:
        return Project.manager_id == user.id
    return exists().where(ProjectMember.project_id == Project.id, ProjectMember.user_id == user.id)


def project_query():
    return select(Project).options(joinedload(Project.manager))


def task_query(user: User):
    return (select(Task).join(Task.project).where(visible_projects(user))
            .options(joinedload(Task.assignee), joinedload(Task.creator), joinedload(Task.project)))


def priority_order():
    return case({Priority.LOW: 1, Priority.MEDIUM: 2, Priority.HIGH: 3, Priority.URGENT: 4}, value=Task.priority)


def paginate(db, statement, filters, serialize):
    total = db.scalar(select(func.count()).select_from(statement.order_by(None).subquery()))
    rows = db.scalars(statement.offset((filters.page - 1) * filters.page_size).limit(filters.page_size)).all()
    return {"items": [serialize(row) for row in rows], "page": filters.page,
            "page_size": filters.page_size, "total": total,
            "total_pages": ceil(total / filters.page_size)}


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "تعارض في البيانات. حدّث الصفحة وتحقق من العضوية قبل إعادة المحاولة.") from None
