from datetime import date, timedelta
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from threading import Event
from uuid import uuid4

import pytest
from fastapi import HTTPException
from sqlalchemy import event, select
from sqlalchemy.exc import IntegrityError, OperationalError
from sqlalchemy.orm import Session

from app.db import get_db
from app.main import app
from app.models import Project, ProjectMember, Role, Task, User
from app import work_services
from tests.test_auth import PASSWORD, login, setup


@pytest.fixture
def work(setup):
    client, engine = setup
    with Session(engine) as db:
        users = {user.role.value: user.id for user in db.scalars(select(User))}
        password_hash = db.get(User, users["Admin"]).password_hash
        other = User(name="مدير آخر", email="other@example.com", role=Role.MANAGER, password_hash=password_hash)
        outsider = User(name="موظف آخر", email="outsider@example.com", role=Role.EMPLOYEE, password_hash=password_hash)
        disabled = User(name="حساب معطل", email="disabled@example.com", role=Role.MANAGER, is_active=False, password_hash=password_hash)
        db.add_all([other, outsider, disabled]); db.commit()
        users.update(other=other.id, outsider=outsider.id, disabled=disabled.id)
    login(client)
    response = client.post("/api/projects", json={"name": "مشروع التدريب", "manager_id": users["Manager"], "status": "Active"})
    assert response.status_code == 201, response.text
    project = response.json()
    assert client.post(f"/api/projects/{project['id']}/members", json={"user_id": users["Employee"]}).status_code == 201
    yield client, engine, users, project


def new_task(client, project, user_id, **extra):
    return client.post(f"/api/projects/{project['id']}/tasks", json={"title": "مهمة اختبار", "assigned_to": user_id, **extra})


def test_project_permissions_and_membership(work):
    client, engine, users, project = work
    pid = project["id"]
    assert client.post("/api/projects", json={"name": "طلب بلا حماية", "manager_id": users["Manager"]}, headers={"X-Requested-With": ""}).status_code == 403
    assert project["created_by"] == users["Admin"]
    assert len(client.get(f"/api/projects/{pid}/members").json()) == 2
    assert client.post(f"/api/projects/{pid}/members", json={"user_id": users["Employee"]}).status_code == 409
    assert client.delete(f"/api/projects/{pid}/members/{users['Manager']}").status_code == 400
    # A manager's membership in another manager's project grants no access.
    assert client.post(f"/api/projects/{pid}/members", json={"user_id": users["other"]}).status_code == 201
    login(client, "other@example.com")
    assert client.get("/api/projects").json()["total"] == 0
    assert client.get(f"/api/projects/{pid}").status_code == 403
    assert client.patch(f"/api/projects/{pid}", json={"name": "مشروع آخر"}).status_code == 403
    login(client, "manager@example.com")
    assert client.get("/api/projects").json()["total"] == 1
    assert client.patch(f"/api/projects/{pid}", json={"description": "تحديث المدير"}).status_code == 200
    assert client.patch(f"/api/projects/{pid}", json={"manager_id": users["other"]}).status_code == 403
    assert client.delete(f"/api/projects/{pid}").status_code == 403
    login(client, "employee@example.com")
    assert client.get(f"/api/projects/{pid}").status_code == 200
    assert client.post("/api/projects", json={"name": "مشروع ممنوع", "manager_id": users["Manager"]}).status_code == 403
    assert client.patch(f"/api/projects/{pid}", json={"name": "تغيير ممنوع"}).status_code == 403
    assert client.post(f"/api/projects/{pid}/members", json={"user_id": users["outsider"]}).status_code == 403
    login(client, "outsider@example.com")
    assert client.get("/api/projects").json()["total"] == 0
    assert client.get(f"/api/projects/{pid}/tasks").status_code == 403
    client.cookies.clear()
    assert client.get("/api/projects").status_code == 401


def test_task_permissions_completion_and_reassignment(work):
    client, engine, users, project = work
    assert new_task(client, project, users["outsider"]).status_code == 400
    assert new_task(client, project, str(uuid4())).status_code == 404
    response = new_task(client, project, users["Employee"], status="done")
    assert response.status_code == 201, response.text
    task = response.json(); tid = task["id"]
    assert task["completed_at"] is not None
    assert client.delete(f"/api/projects/{project['id']}/members/{users['Employee']}").status_code == 409
    login(client, "employee@example.com")
    assert client.get("/api/tasks/my").json()["total"] == 1
    assert client.get(f"/api/tasks/{tid}").status_code == 200
    assert client.patch(f"/api/tasks/{tid}", json={"title": "ممنوع التعديل"}).status_code == 403
    assert client.delete(f"/api/tasks/{tid}").status_code == 403
    reopened = client.patch(f"/api/tasks/{tid}/status", json={"status": "in_progress"})
    assert reopened.status_code == 200 and reopened.json()["completed_at"] is None
    assert client.patch(f"/api/tasks/{tid}/status", json={"status": "done", "assigned_to": users["Manager"]}).status_code == 422
    finished = client.patch(f"/api/tasks/{tid}/status", json={"status": "done"}).json()
    assert finished["completed_at"] is not None
    repeated = client.patch(f"/api/tasks/{tid}/status", json={"status": "done"}).json()
    assert repeated["completed_at"] == finished["completed_at"]
    login(client, "manager@example.com")
    changed = client.patch(f"/api/tasks/{tid}", json={"assigned_to": users["Manager"], "description": "تحديث", "status": "blocked"})
    assert changed.status_code == 200 and changed.json()["completed_at"] is None
    login(client, "employee@example.com")
    assert client.get("/api/tasks/my").json()["total"] == 0
    assert client.patch(f"/api/tasks/{tid}/status", json={"status": "done"}).status_code == 403
    # Membership allows reading all project tasks, not updating other people's work.
    assert client.get(f"/api/projects/{project['id']}/tasks").json()["total"] == 1
    login(client, "manager@example.com")
    assert client.delete(f"/api/projects/{project['id']}/members/{users['Employee']}").status_code == 204
    assert client.delete(f"/api/tasks/{tid}").status_code == 204
    assert client.get(f"/api/tasks/{tid}").status_code == 404


def test_validation_partial_updates_manager_transfer_and_archive(work):
    client, engine, users, project = work
    pid = project["id"]
    for manager_id, code in [(str(uuid4()), 404), (users["disabled"], 400), (users["Employee"], 400)]:
        assert client.post("/api/projects", json={"name": "مشروع مرفوض", "manager_id": manager_id}).status_code == code
    assert client.post("/api/projects", json={"name": "  ", "manager_id": users["Manager"]}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"name": None}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"is_archived": True}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"start_date": "2026-04-10", "end_date": "2026-04-15"}).status_code == 200
    assert client.patch(f"/api/projects/{pid}", json={"end_date": "2026-04-01"}).status_code == 422
    assert new_task(client, project, users["Employee"], due_date="bad").status_code == 422
    assert new_task(client, project, users["Employee"], title="  ").status_code == 422
    assert new_task(client, project, users["Employee"], priority="invalid").status_code == 422
    task = new_task(client, project, users["Employee"]).json()
    assert client.patch(f"/api/tasks/{task['id']}", json={"assigned_to": None}).status_code == 422
    assert client.patch(f"/api/projects/{pid}", json={"manager_id": users["other"]}).status_code == 200
    assert users["other"] in [m["user_id"] for m in client.get(f"/api/projects/{pid}/members").json()]
    login(client, "manager@example.com")
    assert client.get(f"/api/projects/{pid}").status_code == 403
    login(client)
    assert client.delete(f"/api/projects/{pid}").status_code == 204
    assert client.get("/api/projects").json()["total"] == 0
    assert client.get("/api/projects?archived=true").json()["total"] == 1
    assert client.get(f"/api/projects/{pid}").json()["is_archived"] is True
    assert new_task(client, project, users["Employee"]).status_code == 409
    assert client.patch(f"/api/projects/{pid}", json={"name": "تغيير مرفوض"}).status_code == 409
    assert client.post(f"/api/projects/{pid}/members", json={"user_id": users["outsider"]}).status_code == 409
    assert client.patch(f"/api/tasks/{task['id']}/status", json={"status": "done"}).status_code == 409
    assert client.delete(f"/api/tasks/{task['id']}").status_code == 409


def test_filter_pagination_sorting_and_counts_after_authorization(work):
    client, engine, users, project = work
    for index, priority in enumerate(["low", "high", "urgent", "medium", "high"]):
        assert new_task(client, project, users["Employee"], title=f"تسليم رقم {index}", priority=priority,
                        due_date=(date(2020, 1, 1) + timedelta(days=index)).isoformat()).status_code == 201
    new_task(client, project, users["Manager"], title="مهمة المدير", status="done", due_date="2020-01-01")
    new_task(client, project, users["Employee"], title="بدون موعد")
    other = client.post("/api/projects", json={"name": "مشروع آخر", "manager_id": users["other"]}).json()
    new_task(client, other, users["other"], title="مهمة غير مرئية")
    login(client, "employee@example.com")
    result = client.get("/api/tasks/my?q=تسليم&overdue=true&sort_by=priority&sort_order=desc&page_size=2").json()
    assert result["total"] == 5 and result["total_pages"] == 3
    assert [t["priority"] for t in result["items"]] == ["urgent", "high"]
    next_page = client.get("/api/tasks/my?q=تسليم&overdue=true&sort_by=priority&sort_order=desc&page_size=2&page=2").json()
    assert not {t["id"] for t in result["items"]} & {t["id"] for t in next_page["items"]}
    filtered = client.get(f"/api/projects/{project['id']}/tasks?priority=high&status=todo&due_from=2020-01-01&due_to=2020-01-05").json()
    assert filtered["total"] == 2
    assert client.get("/api/tasks/my?overdue=false").json()["total"] == 1
    assert client.get("/api/tasks/my?page=99").json()["items"] == []
    assert client.get("/api/projects?q=مشروع&status=Active").json()["total"] == 1
    assert client.get("/api/projects?created_from=2090-01-01").json()["total"] == 0
    assert client.get("/api/projects?q=%25").json()["total"] == 0  # literal %, not a wildcard
    for path in ["/api/tasks/my?page=0", "/api/tasks/my?page_size=101", "/api/projects?sort_by=password_hash", "/api/tasks/my?due_from=2026-02-02&due_to=2026-01-01"]:
        assert client.get(path).status_code == 422


def test_database_constraints_and_no_n_plus_one(work):
    client, engine, users, project = work
    for _ in range(3):
        assert new_task(client, project, users["Employee"]).status_code == 201
    with Session(engine) as db:
        db.add(ProjectMember(project_id=project["id"], user_id=users["Employee"]))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.add(Task(project_id=project["id"], assigned_to=users["outsider"], created_by=users["Admin"], title="عضوية مفقودة"))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.add(Task(project_id=project["id"], assigned_to=users["Employee"], created_by=users["Admin"], title="إكمال غير متسق", status="done"))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
        db.add(ProjectMember(project_id=str(uuid4()), user_id=users["Employee"]))
        with pytest.raises(IntegrityError): db.commit()
        db.rollback()
    queries = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(f"/api/projects/{project['id']}/tasks?page_size=1").status_code == 200
        small = len(queries); queries.clear()
        assert client.get(f"/api/projects/{project['id']}/tasks?page_size=100").status_code == 200
        assert len(queries) == small  # Joined assignee, creator and project; bounded query count.
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_database_failure_returns_safe_message(work, caplog):
    client, _, _, _ = work
    def failed_db():
        raise OperationalError("private SQL and parameters", {}, Exception("secret-token"))
        yield
    original = app.dependency_overrides[get_db]
    app.dependency_overrides[get_db] = failed_db
    try:
        response = client.get("/api/projects")
        assert response.status_code == 503
        assert "secret-token" not in response.text + caplog.text
        assert "private SQL" not in response.text + caplog.text
    finally:
        app.dependency_overrides[get_db] = original


def test_concurrent_assignment_and_member_removal_are_serialized(work):
    _, engine, users, project = work
    if engine.dialect.name != "postgresql":
        pytest.skip("PostgreSQL row-lock integration test")
    started = Event()
    def remove():
        with Session(engine) as db:
            admin = db.get(User, users["Admin"])
            started.set()
            try:
                work_services.remove_member(db, admin, project["id"], users["Employee"])
                return 204
            except HTTPException as error:
                return error.status_code
    with ThreadPoolExecutor(max_workers=1) as executor:
        with Session(engine) as db:
            db.scalar(select(Project).where(Project.id == project["id"]).with_for_update())
            db.add(Task(project_id=project["id"], assigned_to=users["Employee"], created_by=users["Admin"], title="مهمة متزامنة"))
            db.flush()
            pending = executor.submit(remove)
            try:
                assert started.wait(5)
                with pytest.raises(TimeoutError): pending.result(timeout=0.2)
                db.commit()
            finally:
                db.rollback()
        assert pending.result(timeout=5) == 409


def test_failed_project_creation_is_atomic(work, monkeypatch):
    client, engine, users, _ = work
    # Simulate a constraint conflict after the project has been inserted but
    # before its automatic manager membership is committed.
    original_commit = work_services.repo.commit
    def fail(db):
        db.add(ProjectMember(project_id=str(uuid4()), user_id=users["Manager"]))
        original_commit(db)
    monkeypatch.setattr(work_services.repo, "commit", fail)
    response = client.post("/api/projects", json={"name": "مشروع لن يحفظ", "manager_id": users["Manager"]})
    assert response.status_code == 409
    with Session(engine) as db:
        assert db.scalar(select(Project.id).where(Project.name == "مشروع لن يحفظ")) is None
