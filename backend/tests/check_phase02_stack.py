"""Docker smoke/persistence probe with uniquely named temporary records.

prepare creates a project/task and verifies API auth via Nginx.
verify checks them after restart and deletes only this probe's records.
The ignored local probe file contains record IDs, never credentials or tokens.
"""
import argparse
import json
import secrets
from http.cookiejar import CookieJar
from pathlib import Path
from urllib.request import HTTPCookieProcessor, Request, build_opener

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import AccessSession, Project, ProjectMember, Role, Task, User
from app.security import password_hasher

PROBE = Path(__file__).resolve().parents[1] / ".tmp" / "phase02-probe.json"
BASE_URL = "http://localhost:8080"


def prepare():
    if PROBE.exists():
        raise SystemExit("An earlier probe exists; verify/clean it before starting a new one.")
    ids = {"users": [], "project": None, "task": None}
    PROBE.parent.mkdir(exist_ok=True)
    opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def request(path, method="GET", data=None):
        req = Request(BASE_URL + path, method=method, data=json.dumps(data).encode() if data is not None else None,
                      headers={"Content-Type": "application/json", "X-Requested-With": "WorkSpace", "Origin": BASE_URL})
        with opener.open(req, timeout=10) as response:
            body = response.read()
            return json.loads(body) if body else None
    def save(): PROBE.write_text(json.dumps(ids), encoding="utf-8")
    password = secrets.token_urlsafe(24)
    email = f"phase02-{secrets.token_hex(8)}@example.com"
    with Session(get_engine()) as db:
        admin = User(name="Phase02 temporary admin", email=email, role=Role.ADMIN, password_hash=password_hasher.hash(password))
        db.add(admin); db.commit(); ids["users"].append(admin.id); save()
    request("/api/auth/login", "POST", {"email": email, "password": password})
    manager = request("/api/users", "POST", {"name": "Phase02 temporary manager", "email": "manager-" + email, "role": "Manager", "password": secrets.token_urlsafe(24)})
    ids["users"].append(manager["id"]); save()
    project = request("/api/projects", "POST", {"name": "Phase02 persistence probe", "manager_id": manager["id"], "status": "Active"})
    ids["project"] = project["id"]; save()
    assert len(request(f"/api/projects/{project['id']}/members")) == 1
    task = request(f"/api/projects/{project['id']}/tasks", "POST", {"title": "Phase02 persistent task", "assigned_to": manager["id"], "priority": "urgent"})
    ids["task"] = task["id"]; save()
    task = request(f"/api/tasks/{task['id']}/status", "PATCH", {"status": "done"})
    assert task["completed_at"] is not None
    assert request(f"/api/projects/{project['id']}/tasks?status=done&priority=urgent")["total"] == 1
    request("/api/auth/logout", "POST")
    print("Phase 2 stack probe prepared and verified via Nginx; ready for restart.")


def verify():
    ids = json.loads(PROBE.read_text(encoding="utf-8"))
    try:
        with Session(get_engine()) as db:
            project = db.get(Project, ids["project"])
            task = db.get(Task, ids["task"])
            assert project and task and task.completed_at is not None
            assert db.scalar(select(ProjectMember.id).where(ProjectMember.project_id == project.id, ProjectMember.user_id == project.manager_id)) is not None
            assert db.get(User, ids["users"][0]) is not None
            print("Project, membership, completed task and accounts survived restart.")
    finally:
        with Session(get_engine()) as db:
            if ids["project"]:
                db.execute(delete(Task).where(Task.project_id == ids["project"]))
                db.execute(delete(ProjectMember).where(ProjectMember.project_id == ids["project"]))
                db.execute(delete(Project).where(Project.id == ids["project"]))
            db.execute(delete(AccessSession).where(AccessSession.user_id.in_(ids["users"])))
            db.execute(delete(User).where(User.id.in_(ids["users"])))
            db.commit()
        PROBE.unlink()
        print("Probe records removed; other application data left unchanged.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify"])
    args = parser.parse_args()
    try:
        prepare() if args.action == "prepare" else verify()
    finally:
        get_engine().dispose()
