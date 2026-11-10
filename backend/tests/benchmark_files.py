"""File pagination/concurrency/memory probe on an EMPTY *_files_benchmark DB."""
import gc
import hashlib
import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from time import perf_counter
import tracemalloc
from concurrent.futures import ThreadPoolExecutor
from uuid import uuid4

from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from pypdf import PdfWriter
from sqlalchemy import create_engine, event, inspect, insert, text
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app.config import get_settings
from app.db import Base, get_db, get_engine
from app.file_services import upload_file
from app.file_storage import CHUNK_SIZE, PrivateStorage
from app.main import app, login_attempts
from app.models import Project, ProjectFile, ProjectMember, Role, User
from app.security import password_hasher
from tests.file_samples import image_bytes


def main():
    url = os.environ["BENCHMARK_DATABASE_URL"]
    engine = create_engine(url, pool_pre_ping=True)
    if engine.dialect.name != "postgresql" or not engine.url.database.endswith("_files_benchmark") or inspect(engine).get_table_names():
        raise SystemExit("Use an empty dedicated PostgreSQL database ending in _files_benchmark.")
    os.environ["DATABASE_URL"] = url; get_settings.cache_clear(); get_engine.cache_clear()
    command.upgrade(Config("alembic.ini"), "head"); command.check(Config("alembic.ini"))
    temporary_root = Path(__file__).resolve().parents[1] / ".tmp"; temporary_root.mkdir(exist_ok=True)
    report = {"files": 5000, "projects": 50, "copy_chunk_bytes": CHUNK_SIZE}
    try:
        with TemporaryDirectory(prefix="file-benchmark-", dir=temporary_root) as directory:
            storage = PrivateStorage(Path(directory) / "objects"); storage.initialize()
            get_settings().file_storage_path = storage.root
            admin_id, manager_id, employee_id = [str(uuid4()) for _ in range(3)]
            password = "BenchmarkFilesOnly!123"; hashed = password_hasher.hash(password)
            projects = [{"id": str(uuid4()), "name": f"File benchmark {i}", "manager_id": manager_id, "created_by": admin_id} for i in range(50)]
            png = image_bytes(); checksum = hashlib.sha256(png).hexdigest()
            records = []
            for index in range(5000):
                key = uuid4().hex; (storage.root / key).write_bytes(png)
                records.append({"id": str(uuid4()), "project_id": projects[index // 100]["id"], "uploaded_by": admin_id,
                                "original_name": f"image-{index:05}.png", "storage_key": key, "mime_type": "image/png",
                                "extension": "png", "size_bytes": len(png), "checksum": checksum})
            with Session(engine) as db:
                db.execute(insert(User), [{"id": identifier, "name": role.value, "email": role.value.lower() + "@example.com", "role": role, "password_hash": hashed}
                                         for identifier, role in [(admin_id, Role.ADMIN), (manager_id, Role.MANAGER), (employee_id, Role.EMPLOYEE)]])
                db.execute(insert(Project), projects)
                db.execute(insert(ProjectMember), [{"project_id": project["id"], "user_id": manager_id} for project in projects])
                db.execute(insert(ProjectFile), records); db.commit()
                db.execute(text("ANALYZE")); db.commit()
                report["query_plan"] = db.execute(text("EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) SELECT id,original_name FROM files WHERE project_id=:id AND deleted_at IS NULL ORDER BY created_at DESC,id ASC LIMIT 20"), {"id": projects[0]["id"]}).scalar()
            def override():
                with Session(engine) as db: yield db
            app.dependency_overrides[get_db] = override
            queries = []
            def capture(conn, cursor, statement, parameters, context, executemany):
                if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
            event.listen(engine, "before_cursor_execute", capture)
            login_attempts.clear()
            with TestClient(app, headers={"X-Requested-With": "WorkSpace", "Origin": "http://localhost:5173"}) as client:
                assert client.post("/api/auth/login", json={"email": "admin@example.com", "password": password}).status_code == 200
                for size in [20, 100]:
                    queries.clear(); start = perf_counter()
                    response = client.get(f"/api/projects/{projects[0]['id']}/files?page_size={size}")
                    assert response.status_code == 200 and response.json()["total"] == 100
                    report[f"page_{size}"] = {"elapsed_ms": round((perf_counter() - start) * 1000, 2), "select_queries": len(queries)}
                assert report["page_20"]["select_queries"] == report["page_100"]["select_queries"]
                event.remove(engine, "before_cursor_execute", capture)
                def download(record):
                    response = client.get(f"/api/files/{record['id']}/download")
                    assert response.status_code == 200 and hashlib.sha256(response.content).hexdigest() == checksum
                start = perf_counter()
                with ThreadPoolExecutor(max_workers=4) as pool: list(pool.map(download, records[:8]))
                report["eight_downloads_four_threads_ms"] = round((perf_counter() - start) * 1000, 2)
            large = Path(directory) / "large.pdf"
            writer = PdfWriter(); writer.add_blank_page(width=100, height=100); writer.add_metadata({"/Title": "x" * (4 * 1024 * 1024)})
            writer.write(large); writer.close(); del writer; gc.collect()
            class BoundedReader:
                def __init__(self, stream): self.stream = stream
                def read(self, size=-1):
                    assert 0 < size <= CHUNK_SIZE
                    return self.stream.read(size)
            def store():
                with Session(engine) as db, large.open("rb") as stream:
                    return upload_file(db, db.get(User, admin_id), projects[0]["id"], UploadFile(file=BoundedReader(stream), filename="same-name.pdf"))
            tracemalloc.start(); start = perf_counter(); saved = store(); _, peak = tracemalloc.get_traced_memory(); tracemalloc.stop()
            report["large_upload"] = {"size_bytes": large.stat().st_size, "python_peak_allocated_bytes": peak, "elapsed_ms": round((perf_counter() - start) * 1000, 2)}
            assert peak < large.stat().st_size, "Upload/validation copied the whole large PDF into Python memory"
            start = perf_counter()
            with ThreadPoolExecutor(max_workers=2) as pool: concurrent = list(pool.map(lambda _: store(), range(2)))
            assert concurrent[0].id != concurrent[1].id
            report["two_concurrent_uploads_ms"] = round((perf_counter() - start) * 1000, 2)
            report["memory_scope"] = "tracemalloc of copy/validation/storage service only; excludes client, multipart spooling and native decoder allocations"
        destination = Path(__file__).resolve().parents[2] / "docs" / "phase-03-performance.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps({key: value for key, value in report.items() if key != "query_plan"}, indent=2))
    finally:
        app.dependency_overrides.pop(get_db, None)
        Base.metadata.drop_all(engine)
        with engine.begin() as connection: connection.execute(text("DROP TABLE alembic_version"))
        get_engine().dispose(); engine.dispose()


if __name__ == "__main__": main()
