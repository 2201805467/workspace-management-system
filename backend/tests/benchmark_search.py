"""Measured before/after search indexes, on an EMPTY *_search_benchmark DB."""

import json
import os
from pathlib import Path
from statistics import median
from time import perf_counter
from concurrent.futures import ThreadPoolExecutor
import tracemalloc
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event, inspect, insert, text
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import Base, get_db, get_engine
from app.main import app, login_attempts
from app.models import (
    KnowledgeCategory as Category,
    KnowledgeArticle as Article,
    FileSearchIndex as FI,
    Project,
    ProjectFile,
    ProjectMember,
    User,
    Role,
    utcnow,
)
from app.security import password_hasher


def main():
    url = os.environ["BENCHMARK_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    if (
        engine.dialect.name != "postgresql"
        or not engine.url.database.endswith("_search_benchmark")
        or inspect(engine).get_table_names()
    ):
        raise SystemExit(
            "Use an empty dedicated *_search_benchmark PostgreSQL database."
        )
    os.environ["DATABASE_URL"] = url
    get_settings.cache_clear()
    get_engine.cache_clear()
    get_settings().file_storage_path = (
        Path.cwd() / ".tmp" / ("search-benchmark-" + uuid4().hex)
    )
    command.upgrade(Config("alembic.ini"), "head")
    command.check(Config("alembic.ini"))
    report = {
        "dataset": {
            "categories": 50,
            "articles": 10000,
            "files": 20000,
            "synthetic_extracted_text": True,
        },
        "samples": 5,
    }
    identifiers = [str(uuid4()) for _ in range(3)]
    now = utcnow()
    try:
        hashed = password_hasher.hash("SearchBenchmarkOnly!123")
        categories = [
            dict(
                id=str(uuid4()),
                name=f"Category {i:02}",
                slug=f"category-{i}",
                created_by=identifiers[0],
            )
            for i in range(50)
        ]
        projects = [
            dict(
                id=str(uuid4()),
                name=f"Search project {i}",
                manager_id=identifiers[1],
                created_by=identifiers[0],
            )
            for i in range(10)
        ]
        articles = []
        for i in range(10000):
            articles.append(
                dict(
                    id=str(uuid4()),
                    title=f"دليل الموظفين Employee handbook {i}",
                    slug=f"article-{i}",
                    summary="إدارة المشاريع وملفات الشركة",
                    content=(
                        "quartzneedle rare document guidance"
                        if i % 1000 == 0
                        else "إرشادات الموظفين للعمل والتعاون والبحث عن المعلومات daily workflow guidance"
                    ),
                    author_id=identifiers[0],
                    project_id=projects[(i // 1000) % 10]["id"] if i % 3 == 0 else None,
                    category_id=categories[i % 50]["id"],
                    language="ar" if i % 2 else "en",
                    status="published",
                    published_at=now,
                )
            )
        records = [
            dict(
                id=str(uuid4()),
                project_id=projects[(i // 1000) % 10]["id"],
                uploaded_by=identifiers[0],
                original_name=f"document-{i}.pdf",
                storage_key=uuid4().hex,
                mime_type="application/pdf",
                extension="pdf",
                size_bytes=100,
                checksum="a" * 64,
            )
            for i in range(20000)
        ]
        with Session(engine) as db:
            db.execute(
                insert(User),
                [
                    dict(
                        id=identifier,
                        name=role.value,
                        email=role.value.lower() + "@example.com",
                        role=role,
                        password_hash=hashed,
                    )
                    for identifier, role in zip(
                        identifiers, [Role.ADMIN, Role.MANAGER, Role.EMPLOYEE]
                    )
                ],
            )
            db.execute(insert(Category), categories)
            db.execute(insert(Project), projects)
            db.execute(
                insert(ProjectMember),
                [dict(project_id=projects[0]["id"], user_id=identifiers[2])],
            )
            db.execute(insert(Article), articles)
            db.execute(insert(ProjectFile), records)
            db.commit()
            db.execute(
                text(
                    "UPDATE file_search_index SET indexing_status='ready',indexed_at=now(),extracted_text=CASE WHEN file_id IN (SELECT id FROM files WHERE original_name IN ('document-0.pdf','document-1000.pdf')) THEN 'quartzneedle document guidance' ELSE 'وثائق المشاريع technical documentation daily workflow' END"
                )
            )
            db.commit()
            db.execute(text("ANALYZE"))
            db.commit()

        def override():
            with Session(engine) as db:
                yield db

        app.dependency_overrides[get_db] = override
        login_attempts.clear()
        indexes = [
            index
            for table in [Article.__table__, FI.__table__]
            for index in table.indexes
            if index.dialect_options["postgresql"]["using"] == "gin"
        ]
        plan_sql = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id FROM knowledge_articles WHERE search_vector @@ websearch_to_tsquery('public.workspace_arabic',workspace_normalize('quartzneedle'))"
        with TestClient(
            app,
            headers={
                "X-Requested-With": "WorkSpace",
                "Origin": "http://localhost:5173",
            },
        ) as client:
            assert (
                client.post(
                    "/api/auth/login",
                    json={
                        "email": "admin@example.com",
                        "password": "SearchBenchmarkOnly!123",
                    },
                ).status_code
                == 200
            )

            def measure():
                samples = []
                for _ in range(5):
                    start = perf_counter()
                    response = client.get("/api/search?q=quartzneedle")
                    assert response.status_code == 200, response.text
                    samples.append(round((perf_counter() - start) * 1000, 2))
                return {
                    "median_ms": median(samples),
                    "max_ms": max(samples),
                    "total": response.json()["total"],
                }

            with engine.begin() as connection:
                for index in indexes:
                    index.drop(connection)
                connection.execute(text("ANALYZE"))
            report["without_gin"] = measure()
            with engine.connect() as connection:
                report["plan_before"] = connection.execute(text(plan_sql)).scalar()
            with engine.begin() as connection:
                for index in indexes:
                    index.create(connection)
                connection.execute(text("ANALYZE"))
            report["with_gin"] = measure()
            with engine.connect() as connection:
                report["plan_after"] = connection.execute(text(plan_sql)).scalar()
            queries = []

            def capture(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"):
                    queries.append(statement)

            event.listen(engine, "before_cursor_execute", capture)
            for size in [20, 100]:
                queries.clear()
                start = perf_counter()
                response = client.get(
                    f"/api/search?q=guidance&type=all&page_size={size}"
                )
                assert response.status_code == 200
                report[f"page_{size}"] = {
                    "elapsed_ms": round((perf_counter() - start) * 1000, 2),
                    "select_queries": len(queries),
                    "total": response.json()["total"],
                }
            event.remove(engine, "before_cursor_execute", capture)
            assert (
                report["page_20"]["select_queries"]
                == report["page_100"]["select_queries"]
            )
            tracemalloc.start()
            response = client.get("/api/search?q=guidance&page_size=20")
            _, peak = tracemalloc.get_traced_memory()
            tracemalloc.stop()
            report["python_peak_page_20_bytes"] = peak

            def concurrent(_):
                response = client.get("/api/search?q=quartzneedle")
                assert response.status_code == 200

            start = perf_counter()
            with ThreadPoolExecutor(max_workers=4) as pool:
                list(pool.map(concurrent, range(8)))
            report["eight_searches_four_threads_ms"] = round(
                (perf_counter() - start) * 1000, 2
            )
            client.cookies.clear()
            assert (
                client.post(
                    "/api/auth/login",
                    json={
                        "email": "employee@example.com",
                        "password": "SearchBenchmarkOnly!123",
                    },
                ).status_code
                == 200
            )
            response = client.get("/api/search?q=quartzneedle")
            assert response.status_code == 200
            report["employee_authorized_total"] = response.json()["total"]
            assert report["employee_authorized_total"] < report["with_gin"]["total"]
        destination = (
            Path(__file__).resolve().parents[2] / "docs" / "phase-04-performance.json"
        )
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(
            json.dumps(
                {
                    key: value
                    for key, value in report.items()
                    if key not in {"plan_before", "plan_after"}
                },
                indent=2,
            )
        )
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        with engine.begin() as connection:
            connection.execute(text("DROP TABLE IF EXISTS alembic_version"))
        get_engine().dispose()
        engine.dispose()


if __name__ == "__main__":
    main()
