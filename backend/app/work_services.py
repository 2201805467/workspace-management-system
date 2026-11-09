"""Business rules, authorization, and atomic project/task changes."""
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from fastapi import HTTPException
from sqlalchemy import or_, select
from sqlalchemy.orm import joinedload

from . import work_repository as repo
from .models import Project, ProjectMember, Role, Task, TaskStatus, User, utcnow
from .work_schemas import ProjectOut, TaskOut

COMPANY_TZ = ZoneInfo("Africa/Tripoli")


def today():
    return datetime.now(COMPANY_TZ).date()


def get_project(db, project_id, user, *, write=False):
    # Mutations lock the project first, so assignment, removal, manager changes,
    # and archival cannot race each other on PostgreSQL.
    statement = select(Project).where(Project.id == str(project_id))
    if write:
        statement = statement.with_for_update()
    project = db.scalar(statement.execution_options(populate_existing=True))
    if not project:
        raise HTTPException(404, "المشروع غير موجود")
    allowed = user.role == Role.ADMIN or (user.role == Role.MANAGER and project.manager_id == user.id)
    if user.role == Role.EMPLOYEE:
        allowed = db.scalar(select(ProjectMember.id).where(
            ProjectMember.project_id == project.id, ProjectMember.user_id == user.id)) is not None
    if not allowed:
        raise HTTPException(403, "لا تملك صلاحية الوصول إلى هذا المشروع")
    if write and project.is_archived:
        raise HTTPException(409, "المشروع مؤرشف ومتاح للقراءة فقط")
    return project


def require_editor(user, project):
    if user.role != Role.ADMIN and not (user.role == Role.MANAGER and project.manager_id == user.id):
        raise HTTPException(403, "تعديل المشروع ومهامه متاح للمسؤول ومدير المشروع فقط")


def active_user(db, user_id, *, manager=False):
    user = db.get(User, str(user_id))
    if not user:
        raise HTTPException(404, "المستخدم غير موجود")
    if not user.is_active:
        raise HTTPException(400, "حساب المستخدم معطّل")
    if manager and user.role not in {Role.ADMIN, Role.MANAGER}:
        raise HTTPException(400, "مدير المشروع يجب أن يكون بدور Manager أو Admin")
    return user


def member(db, project_id, user_id):
    return db.scalar(select(ProjectMember).where(
        ProjectMember.project_id == project_id, ProjectMember.user_id == str(user_id)))


def validate_assignee(db, project_id, user_id):
    active_user(db, user_id)
    if not member(db, project_id, user_id):
        raise HTTPException(400, "يجب إضافة الموظف إلى المشروع قبل إسناد المهمة إليه")


def project_out(db, project_id):
    project = db.scalar(repo.project_query().where(Project.id == project_id).execution_options(populate_existing=True))
    return ProjectOut.model_validate(project)


def create_project(db, user, payload):
    if user.role != Role.ADMIN:
        raise HTTPException(403, "إنشاء المشاريع متاح للمسؤول فقط")
    manager = active_user(db, payload.manager_id, manager=True)
    data = payload.model_dump()
    data["manager_id"] = manager.id
    project = Project(**data, created_by=user.id)
    db.add(project)
    db.flush()
    db.add(ProjectMember(project_id=project.id, user_id=manager.id))
    repo.commit(db)
    return project_out(db, project.id)


def update_project(db, user, project_id, payload):
    project = get_project(db, project_id, user, write=True)
    require_editor(user, project)
    data = payload.model_dump(exclude_unset=True)
    if "manager_id" in data:
        if user.role != Role.ADMIN:
            raise HTTPException(403, "تغيير مدير المشروع متاح للمسؤول فقط")
        manager = active_user(db, data["manager_id"], manager=True)
        data["manager_id"] = manager.id
        if not member(db, project.id, manager.id):
            db.add(ProjectMember(project_id=project.id, user_id=manager.id))
    start = data.get("start_date", project.start_date)
    end = data.get("end_date", project.end_date)
    if start and end and end < start:
        raise HTTPException(422, "تاريخ نهاية المشروع يجب أن يساوي تاريخ البداية أو يليه")
    for field, value in data.items():
        setattr(project, field, value)
    repo.commit(db)
    return project_out(db, project.id)


def archive_project(db, user, project_id):
    if user.role != Role.ADMIN:
        raise HTTPException(403, "أرشفة المشاريع متاحة للمسؤول فقط")
    project = get_project(db, project_id, user, write=True)
    project.is_archived, project.archived_at = True, utcnow()
    repo.commit(db)


def list_projects(db, user, filters):
    statement = repo.project_query().where(repo.visible_projects(user), Project.is_archived == filters.archived)
    if filters.q:
        statement = statement.where(Project.name.icontains(filters.q.strip(), autoescape=True))
    if filters.status:
        statement = statement.where(Project.status == filters.status)
    if filters.manager_id:
        statement = statement.where(Project.manager_id == str(filters.manager_id))
    if filters.created_from and filters.created_to and filters.created_from > filters.created_to:
        raise HTTPException(422, "نطاق تاريخ الإنشاء غير صحيح")
    if filters.created_from:
        lower = datetime.combine(filters.created_from, time.min, tzinfo=COMPANY_TZ).astimezone(timezone.utc)
        statement = statement.where(Project.created_at >= lower)
    if filters.created_to:
        upper = datetime.combine(filters.created_to + timedelta(days=1), time.min, tzinfo=COMPANY_TZ).astimezone(timezone.utc)
        statement = statement.where(Project.created_at < upper)
    column = getattr(Project, filters.sort_by)
    ordering = column.asc() if filters.sort_order == "asc" else column.desc()
    statement = statement.order_by(ordering.nulls_last(), Project.id.asc())
    return repo.paginate(db, statement, filters, ProjectOut.model_validate)


def list_members(db, user, project_id):
    project = get_project(db, project_id, user)
    return db.scalars(select(ProjectMember).where(ProjectMember.project_id == project.id)
                      .options(joinedload(ProjectMember.user)).order_by(ProjectMember.joined_at, ProjectMember.id)).all()


def add_member(db, user, project_id, payload):
    project = get_project(db, project_id, user, write=True)
    require_editor(user, project)
    person = active_user(db, payload.user_id)
    if member(db, project.id, person.id):
        raise HTTPException(409, "المستخدم عضو في المشروع بالفعل")
    membership = ProjectMember(project_id=project.id, user_id=person.id)
    db.add(membership)
    repo.commit(db)
    return db.scalar(select(ProjectMember).where(ProjectMember.id == membership.id).options(joinedload(ProjectMember.user)))


def remove_member(db, user, project_id, user_id):
    project = get_project(db, project_id, user, write=True)
    require_editor(user, project)
    if str(user_id) == project.manager_id:
        raise HTTPException(400, "لا يمكن إزالة مدير المشروع الحالي")
    membership = member(db, project.id, user_id)
    if not membership:
        raise HTTPException(404, "المستخدم ليس عضوًا في المشروع")
    if db.scalar(select(Task.id).where(Task.project_id == project.id, Task.assigned_to == str(user_id)).limit(1)):
        raise HTTPException(409, "للموظف مهام مسندة إليه. أعد توزيعها قبل إزالة عضويته.")
    db.delete(membership)
    repo.commit(db)


def task_out(task):
    fields = {name: getattr(task, name) for name in TaskOut.model_fields
              if name not in {"project_name", "project_archived", "is_overdue"}}
    return TaskOut(**fields, project_name=task.project.name, project_archived=task.project.is_archived,
                   is_overdue=task.due_date is not None and task.due_date < today() and task.status != TaskStatus.DONE)


def load_task(db, task_id, user, *, write=False):
    project_id = db.scalar(select(Task.project_id).where(Task.id == str(task_id)))
    if not project_id:
        raise HTTPException(404, "المهمة غير موجودة")
    project = get_project(db, project_id, user, write=write)
    task = db.get(Task, str(task_id), populate_existing=True)
    if not task:
        raise HTTPException(404, "المهمة غير موجودة")
    return task, project


def get_task(db, task_id, user):
    load_task(db, task_id, user)
    return task_out(db.scalar(repo.task_query(user).where(Task.id == str(task_id))))


def sync_completion(task, previous_status=None):
    if task.status == TaskStatus.DONE:
        if previous_status != TaskStatus.DONE or task.completed_at is None:
            task.completed_at = utcnow()
    else:
        task.completed_at = None


def create_task(db, user, project_id, payload):
    project = get_project(db, project_id, user, write=True)
    require_editor(user, project)
    validate_assignee(db, project.id, payload.assigned_to)
    data = payload.model_dump()
    data["assigned_to"] = str(payload.assigned_to)
    task = Task(**data, project_id=project.id, created_by=user.id)
    sync_completion(task)
    db.add(task)
    repo.commit(db)
    return get_task(db, task.id, user)


def update_task(db, user, task_id, payload, *, status_only=False):
    task, project = load_task(db, task_id, user, write=True)
    if status_only and user.role == Role.EMPLOYEE:
        if task.assigned_to != user.id:
            raise HTTPException(403, "يمكنك تغيير حالة مهامك فقط")
    else:
        require_editor(user, project)
    data = payload.model_dump(exclude_unset=True)
    if "assigned_to" in data:
        validate_assignee(db, project.id, data["assigned_to"])
        data["assigned_to"] = str(data["assigned_to"])
    previous_status = task.status
    for field, value in data.items():
        setattr(task, field, value)
    sync_completion(task, previous_status)
    repo.commit(db)
    return get_task(db, task.id, user)


def delete_task(db, user, task_id):
    task, project = load_task(db, task_id, user, write=True)
    require_editor(user, project)
    db.delete(task)
    repo.commit(db)


def list_tasks(db, user, filters, *, project_id=None, mine=False):
    statement = repo.task_query(user)
    if project_id is not None:
        project = get_project(db, project_id, user)
        statement = statement.where(Task.project_id == project.id)
    else:
        statement = statement.where(Project.is_archived == filters.archived)
    if mine:
        statement = statement.where(Task.assigned_to == user.id)
    if filters.project_id:
        statement = statement.where(Task.project_id == str(filters.project_id))
    if filters.assigned_to:
        statement = statement.where(Task.assigned_to == str(filters.assigned_to))
    if filters.q:
        statement = statement.where(Task.title.icontains(filters.q.strip(), autoescape=True))
    if filters.status:
        statement = statement.where(Task.status == filters.status)
    if filters.priority:
        statement = statement.where(Task.priority == filters.priority)
    if filters.due_from and filters.due_to and filters.due_from > filters.due_to:
        raise HTTPException(422, "نطاق الموعد النهائي غير صحيح")
    if filters.due_from:
        statement = statement.where(Task.due_date >= filters.due_from)
    if filters.due_to:
        statement = statement.where(Task.due_date <= filters.due_to)
    overdue = (Task.due_date < today()) & (Task.status != TaskStatus.DONE)
    if filters.overdue is not None:
        # A task without a deadline is not overdue.
        statement = statement.where(overdue if filters.overdue else or_(Task.due_date.is_(None), ~overdue))
    column = repo.priority_order() if filters.sort_by == "priority" else getattr(Task, filters.sort_by)
    ordering = column.asc() if filters.sort_order == "asc" else column.desc()
    statement = statement.order_by(ordering.nulls_last(), Task.id.asc())
    return repo.paginate(db, statement, filters, task_out)
