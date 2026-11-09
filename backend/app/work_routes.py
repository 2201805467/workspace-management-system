from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from . import work_services as service
from .models import Project, Role, User
from .work_repository import visible_projects
from .security import CurrentUser, Db
from .work_schemas import (MemberCreate, MemberOut, Page, PersonOut, ProjectCreate,
                           ProjectFilters, ProjectOut, ProjectUpdate, TaskCreate,
                           TaskFilters, TaskOut, TaskStatusUpdate, TaskUpdate)

router = APIRouter(prefix="/api", tags=["Projects & Tasks"])


@router.get("/project-managers", response_model=list[PersonOut])
def project_managers(user: CurrentUser, db: Db):
    return db.scalars(select(User).join(Project, Project.manager_id == User.id)
                      .where(visible_projects(user)).distinct().order_by(User.name, User.id)).all()


@router.get("/people", response_model=list[PersonOut])
def people(user: CurrentUser, db: Db):
    if user.role == Role.EMPLOYEE:
        raise HTTPException(403, "اختيار أعضاء الفريق متاح للمسؤول والمدير فقط")
    return db.scalars(select(User).where(User.is_active.is_(True)).order_by(User.name, User.id)).all()


@router.post("/projects", response_model=ProjectOut, status_code=201)
def create_project(payload: ProjectCreate, user: CurrentUser, db: Db):
    return service.create_project(db, user, payload)


@router.get("/projects", response_model=Page[ProjectOut])
def projects(filters: Annotated[ProjectFilters, Query()], user: CurrentUser, db: Db):
    return service.list_projects(db, user, filters)


@router.get("/projects/{project_id}", response_model=ProjectOut)
def project(project_id: UUID, user: CurrentUser, db: Db):
    project = service.get_project(db, project_id, user)
    return service.project_out(db, project.id)


@router.patch("/projects/{project_id}", response_model=ProjectOut)
def update_project(project_id: UUID, payload: ProjectUpdate, user: CurrentUser, db: Db):
    return service.update_project(db, user, project_id, payload)


@router.delete("/projects/{project_id}", status_code=204)
def archive_project(project_id: UUID, user: CurrentUser, db: Db):
    service.archive_project(db, user, project_id)


@router.get("/projects/{project_id}/members", response_model=list[MemberOut])
def members(project_id: UUID, user: CurrentUser, db: Db):
    return service.list_members(db, user, project_id)


@router.post("/projects/{project_id}/members", response_model=MemberOut, status_code=201)
def add_member(project_id: UUID, payload: MemberCreate, user: CurrentUser, db: Db):
    return service.add_member(db, user, project_id, payload)


@router.delete("/projects/{project_id}/members/{user_id}", status_code=204)
def remove_member(project_id: UUID, user_id: UUID, user: CurrentUser, db: Db):
    service.remove_member(db, user, project_id, user_id)


@router.post("/projects/{project_id}/tasks", response_model=TaskOut, status_code=201)
def create_task(project_id: UUID, payload: TaskCreate, user: CurrentUser, db: Db):
    return service.create_task(db, user, project_id, payload)


@router.get("/projects/{project_id}/tasks", response_model=Page[TaskOut])
def project_tasks(project_id: UUID, filters: Annotated[TaskFilters, Query()], user: CurrentUser, db: Db):
    return service.list_tasks(db, user, filters, project_id=project_id)


# Static route precedes /tasks/{task_id} so "my" is never parsed as a UUID.
@router.get("/tasks/my", response_model=Page[TaskOut])
def my_tasks(filters: Annotated[TaskFilters, Query()], user: CurrentUser, db: Db):
    return service.list_tasks(db, user, filters, mine=True)


@router.get("/tasks/{task_id}", response_model=TaskOut)
def task(task_id: UUID, user: CurrentUser, db: Db):
    return service.get_task(db, task_id, user)


@router.patch("/tasks/{task_id}", response_model=TaskOut)
def update_task(task_id: UUID, payload: TaskUpdate, user: CurrentUser, db: Db):
    return service.update_task(db, user, task_id, payload)


@router.patch("/tasks/{task_id}/status", response_model=TaskOut)
def change_status(task_id: UUID, payload: TaskStatusUpdate, user: CurrentUser, db: Db):
    return service.update_task(db, user, task_id, payload, status_only=True)


@router.delete("/tasks/{task_id}", status_code=204)
def delete_task(task_id: UUID, user: CurrentUser, db: Db):
    service.delete_task(db, user, task_id)
