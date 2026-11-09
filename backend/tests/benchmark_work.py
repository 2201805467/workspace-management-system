"""Reproducible local benchmark; requires an EMPTY *_benchmark PostgreSQL DB."""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from statistics import median
from time import perf_counter
from uuid import uuid4

from fastapi.testclient import TestClient
from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, event, inspect, insert, text
from sqlalchemy.orm import Session

from app.db import Base, get_db
from app.main import app, login_attempts
from app.models import Priority, Project, ProjectMember, ProjectStatus, Role, Task, TaskStatus, User
from app.security import password_hasher
from app.work_services import today


def main():
    url = os.environ["BENCHMARK_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql" or not engine.url.database.endswith("_benchmark"):
        raise SystemExit("Use a dedicated PostgreSQL database ending in _benchmark.")
    if inspect(engine).get_table_names():
        raise SystemExit("Benchmark database must be empty; existing tables were left unchanged.")
    report = {"dataset": {"projects": 100, "tasks": 10000, "users": 20}, "samples_per_request": 10, "measurements": {}}
    os.environ["DATABASE_URL"] = url
    from app.config import get_settings
    from app.db import get_engine
    get_settings.cache_clear(); get_engine.cache_clear()
    command.upgrade(Config("alembic.ini"), "head")
    command.check(Config("alembic.ini"))
    queries = []

    def override():
        with Session(engine) as db:
            yield db

    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"):
            queries.append(statement)

    try:
        now = datetime.now(timezone.utc)
        hashed = password_hasher.hash("BenchmarkOnlyPassword!123")
        users = [{"id": str(uuid4()), "name": f"Benchmark user {index}", "email": f"benchmark{index}@example.com",
                  "role": Role.ADMIN if index == 0 else Role.MANAGER if index == 1 else Role.EMPLOYEE,
                  "is_active": True, "password_hash": hashed, "created_at": now} for index in range(20)]
        projects = [{"id": str(uuid4()), "name": f"Benchmark project {index:03}", "manager_id": users[1]["id"],
                     "created_by": users[0]["id"], "status": ProjectStatus.ACTIVE, "is_archived": False,
                     "created_at": now, "updated_at": now} for index in range(100)]
        memberships = [{"project_id": project["id"], "user_id": user["id"]} for project in projects for user in users[1:]]
        tasks = []
        statuses = list(TaskStatus); priorities = list(Priority)
        for pindex, project in enumerate(projects):
            for index in range(100):
                status = statuses[index % 4]
                tasks.append({"project_id": project["id"], "assigned_to": users[2 + index % 18]["id"],
                              "created_by": users[1]["id"], "title": f"Benchmark task {pindex}-{index}",
                              "status": status, "priority": priorities[(index // 4) % 4],
                              "due_date": today() + timedelta(days=index % 20 - 10),
                              "created_at": now, "updated_at": now,
                              "completed_at": now if status == TaskStatus.DONE else None})
        with Session(engine) as db:
            db.execute(insert(User), users); db.execute(insert(Project), projects)
            db.execute(insert(ProjectMember), memberships); db.execute(insert(Task), tasks); db.commit()
            db.execute(text("ANALYZE")); db.commit()
            plan = db.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id, title FROM tasks "
                                   "WHERE project_id = :project AND status = 'in_progress' ORDER BY due_date, id LIMIT 20"),
                              {"project": projects[0]["id"]}).scalar()
            report["query_plan"] = plan
        app.dependency_overrides[get_db] = override
        login_attempts.clear()
        event.listen(engine, "before_cursor_execute", capture)
        with TestClient(app, headers={"X-Requested-With": "WorkSpace", "Origin": "http://localhost:5173"}) as client:
            assert client.post("/api/auth/login", json={"email": users[0]["email"], "password": "BenchmarkOnlyPassword!123"}).status_code == 200
            requests = {
                "projects_page_20": "/api/projects?page_size=20",
                "projects_page_100": "/api/projects?page_size=100",
                "project_tasks_page_20": f"/api/projects/{projects[0]['id']}/tasks?page_size=20",
                "project_tasks_page_100": f"/api/projects/{projects[0]['id']}/tasks?page_size=100",
                "combined_filters": f"/api/projects/{projects[0]['id']}/tasks?status=in_progress&priority=high&overdue=true&sort_by=due_date&page_size=20",
            }
            for label, path in requests.items():
                times, counts = [], []
                for _ in range(10):
                    queries.clear(); start = perf_counter(); response = client.get(path)
                    assert response.status_code == 200, response.text
                    times.append(round((perf_counter() - start) * 1000, 2)); counts.append(len(queries))
                report["measurements"][label] = {"median_ms": median(times), "max_ms": max(times), "select_queries": max(counts), "total": response.json()["total"]}
            assert report["measurements"]["project_tasks_page_20"]["select_queries"] == report["measurements"]["project_tasks_page_100"]["select_queries"]
            assert report["measurements"]["projects_page_20"]["select_queries"] == report["measurements"]["projects_page_100"]["select_queries"]
            client.cookies.clear()
            assert client.post("/api/auth/login", json={"email": users[2]["email"], "password": "BenchmarkOnlyPassword!123"}).status_code == 200
            queries.clear(); start = perf_counter(); response = client.get("/api/tasks/my?sort_by=priority&page_size=20")
            assert response.status_code == 200
            report["employee_my_tasks"] = {"elapsed_ms": round((perf_counter() - start) * 1000, 2), "select_queries": len(queries), "total": response.json()["total"]}
        destination = Path(__file__).resolve().parents[2] / "docs" / "phase-02-performance.json"
        destination.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
        print(json.dumps(report["measurements"], indent=2))
        print(f"Report saved: {destination.name}")
    finally:
        event.remove(engine, "before_cursor_execute", capture) if event.contains(engine, "before_cursor_execute", capture) else None
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE alembic_version"))
        get_engine().dispose()
        engine.dispose()


if __name__ == "__main__":
    main()
