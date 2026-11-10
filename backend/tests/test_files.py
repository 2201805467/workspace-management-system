import errno
import hashlib
import io
import os
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.exc import OperationalError
from sqlalchemy.orm import Session
from starlette.datastructures import UploadFile

from app import file_services
from app.config import get_settings
from app.file_audit import audit
from app.file_storage import CHUNK_SIZE, PrivateStorage
from app.main import app
from app.models import ProjectFile
from tests.file_samples import docx_bytes, image_bytes, pdf_bytes
from tests.test_auth import login, setup
from tests.test_work import work


@pytest.fixture
def files(work, tmp_path, monkeypatch):
    monkeypatch.setattr(get_settings(), "file_storage_path", tmp_path)
    return (*work, tmp_path)


def upload(client, project, content=None, name="document.pdf", mime="application/pdf"):
    return client.post(f"/api/projects/{project['id']}/files", files={"file": (name, pdf_bytes() if content is None else content, mime)})


@pytest.mark.parametrize("name,factory,mime", [
    ("دليل.pdf", pdf_bytes, "application/pdf"), ("photo.png", image_bytes, "image/png"),
    ("photo.jpg", lambda: image_bytes("JPEG"), "image/jpeg"),
    ("photo.jpeg", lambda: image_bytes("JPEG"), "image/jpeg"), ("guide.docx", docx_bytes, "application/vnd.openxmlformats-officedocument.wordprocessingml.document"),
])
def test_upload_download_metadata_checksum(files, name, factory, mime):
    client, engine, users, project, root = files
    data = factory()
    response = upload(client, project, data, name, "application/octet-stream")
    assert response.status_code == 201, response.text
    record = response.json()
    assert record["original_name"] == name and record["mime_type"] == mime
    assert record["size_bytes"] == len(data) and record["checksum"] == hashlib.sha256(data).hexdigest()
    assert record["uploaded_by"] == users["Admin"]
    assert "storage_key" not in record and str(root) not in response.text
    with Session(engine) as db:
        row = db.get(ProjectFile, record["id"])
        assert (root / row.storage_key).read_bytes() == data
    info = client.get(f"/api/files/{record['id']}")
    assert info.status_code == 200 and info.json()["id"] == record["id"]
    downloaded = client.get(f"/api/files/{record['id']}/download")
    assert downloaded.status_code == 200 and downloaded.content == data
    assert downloaded.headers["content-type"] == mime
    assert downloaded.headers["content-disposition"].startswith("attachment;")
    assert downloaded.headers["x-content-type-options"] == "nosniff"
    assert list((root / ".tmp").iterdir()) == []


@pytest.mark.parametrize("name,data,code", [
    ("empty.pdf", b"", 400), ("program.exe", b"MZexe", 415), ("fake.pdf", b"MZexe", 415),
    ("fake.png", b"print('hello')", 415), ("broken.pdf", b"%PDF-1.7\ncorrupt", 415),
    ("broken.png", b"\x89PNG\r\n\x1a\ncorrupt", 415), ("broken.docx", b"PK\x03\x04corrupt", 415),
    ("../secret.pdf", b"irrelevant", 400), ("..%2fsecret.pdf", b"irrelevant", 400),
    ("C:\\secret.pdf", b"irrelevant", 400),
])
def test_invalid_files_leave_no_objects(files, name, data, code):
    client, engine, users, project, root = files
    response = upload(client, project, data, name)
    assert response.status_code == code, response.text
    assert not list(root.glob("[0-9a-f]" * 32))
    assert not (root / ".tmp").exists() or not list((root / ".tmp").iterdir())
    with Session(engine) as db:
        assert db.scalar(select(ProjectFile.id)) is None


def test_docx_bombs_traversal_xml_entities_and_type_mismatch(files):
    client, _, _, project, _ = files
    for data in [docx_bytes({"../evil.xml": "x"}), docx_bytes({"word/embeddings/evil.bin": "x"}),
                 docx_bytes({"word/bomb.xml": "x" * 500000}),
                 docx_bytes({"word/entity.xml": '<!DOCTYPE a [<!ENTITY x SYSTEM "file:///secret">]><a>&x;</a>'})]:
        assert upload(client, project, data, "document.docx").status_code == 415
    assert upload(client, project, image_bytes(), "photo.jpg").status_code == 415


def test_size_limit_measured_without_content_length(files, monkeypatch):
    client, _, _, project, root = files
    monkeypatch.setattr(get_settings(), "max_upload_bytes", 100)
    # The multipart envelope is small enough to parse; actual file-byte limit
    # must still reject this valid PDF and clean the private temporary object.
    assert upload(client, project).status_code == 413
    boundary = "test-boundary"
    body = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="big.pdf"\r\n'
            'Content-Type: application/pdf\r\n\r\n').encode() + b"x" * 70000 + f"\r\n--{boundary}--\r\n".encode()
    result = client.post(f"/api/projects/{project['id']}/files", content=iter([body[:1000], body[1000:]]),
                         headers={"Content-Type": f"multipart/form-data; boundary={boundary}"})
    assert result.status_code == 413
    assert not list((root / ".tmp").iterdir())


def test_file_permissions_soft_delete_and_archival(files):
    client, engine, users, project, root = files
    admin_file = upload(client, project).json()
    login(client, "employee@example.com")
    own = upload(client, project, name="own.pdf")
    assert own.status_code == 201
    own_id = own.json()["id"]
    assert client.delete(f"/api/files/{admin_file['id']}").status_code == 403
    assert client.get(f"/api/files/{admin_file['id']}/download").status_code == 200
    assert client.delete(f"/api/files/{own_id}").status_code == 204
    assert client.get(f"/api/files/{own_id}/download").status_code == 404
    assert client.get(f"/api/files/{own_id}").status_code == 404
    assert client.get(f"/api/projects/{project['id']}/files").json()["total"] == 1
    with Session(engine) as db:
        deleted = db.get(ProjectFile, own_id)
        assert deleted.deleted_at is not None and (root / deleted.storage_key).exists()
    login(client, "other@example.com")
    assert client.get(f"/api/files/{admin_file['id']}/download").status_code == 403
    assert client.get(f"/api/files/{admin_file['id']}").status_code == 403
    assert upload(client, project).status_code == 403
    login(client, "outsider@example.com")
    assert client.get(f"/api/projects/{project['id']}/files").status_code == 403
    login(client, "manager@example.com")
    assert upload(client, project, name="manager.pdf").status_code == 201
    assert client.delete(f"/api/files/{admin_file['id']}").status_code == 204
    login(client)
    retained = upload(client, project).json()
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/files/{retained['id']}/download").status_code == 200
    assert upload(client, project).status_code == 409
    assert client.delete(f"/api/files/{retained['id']}").status_code == 409
    client.cookies.clear()
    assert client.get(f"/api/files/{retained['id']}/download").status_code == 401
    assert upload(client, project).status_code == 401


def test_same_names_pagination_filters_and_no_n_plus_one(files):
    client, engine, users, project, _ = files
    one = upload(client, project).json(); two = upload(client, project).json()
    assert one["id"] != two["id"]
    with Session(engine) as db:
        rows = db.scalars(select(ProjectFile)).all()
        assert rows[0].storage_key != rows[1].storage_key
    assert upload(client, project, image_bytes(), "photo.png").status_code == 201
    path = f"/api/projects/{project['id']}/files"
    result = client.get(path + "?type=pdf&q=document&page_size=1&sort_by=original_name&sort_order=asc").json()
    assert result["total"] == 2 and result["total_pages"] == 2
    next_page = client.get(path + "?type=pdf&q=document&page_size=1&page=2&sort_by=original_name&sort_order=asc").json()
    assert next_page["items"][0]["id"] != result["items"][0]["id"]
    assert client.get(path + f"?uploaded_by={users['outsider']}").json()["total"] == 0
    assert client.get(path + "?page_size=101").status_code == 422
    assert client.get(path + "?sort_by=storage_key").status_code == 422
    queries = []
    def capture(conn, cursor, statement, parameters, context, executemany):
        if statement.lstrip().upper().startswith("SELECT"): queries.append(statement)
    event.listen(engine, "before_cursor_execute", capture)
    try:
        assert client.get(path + "?page_size=1").status_code == 200
        count = len(queries); queries.clear()
        assert client.get(path + "?page_size=100").status_code == 200
        assert len(queries) == count
    finally:
        event.remove(engine, "before_cursor_execute", capture)


def test_missing_storage_and_write_failure(files, monkeypatch, caplog):
    client, engine, users, project, root = files
    result = upload(client, project).json()
    with Session(engine) as db:
        key = db.get(ProjectFile, result["id"]).storage_key
    (root / key).unlink()
    response = client.get(f"/api/files/{result['id']}/download")
    assert response.status_code == 404 and key not in response.text
    def full(*args): raise OSError(errno.ENOSPC, "private-storage-path secret")
    monkeypatch.setattr(file_services.os, "fsync", full)
    response = upload(client, project)
    assert response.status_code == 503
    assert "private-storage-path" not in response.text + caplog.text
    assert not list((root / ".tmp").iterdir())


def test_database_insert_failure_cleans_promoted_object(files, monkeypatch):
    client, engine, _, project, root = files
    def fail(db, flush_context, instances):
        if any(isinstance(row, ProjectFile) for row in db.new):
            raise OperationalError("hidden SQL", {}, Exception("unavailable"))
    event.listen(Session, "before_flush", fail)
    try:
        assert upload(client, project).status_code == 503
    finally:
        event.remove(Session, "before_flush", fail)
    assert list((root / ".tmp").iterdir()) == []
    assert [path for path in root.iterdir() if path.is_file()] == []


def test_stream_copy_is_bounded_and_cleans_interrupted_read(files):
    client, engine, users, project, root = files
    class Interrupted(io.BytesIO):
        def read(self, size=-1):
            assert 0 < size <= CHUNK_SIZE
            if self.tell(): raise OSError(errno.EIO, "disconnect")
            return super().read(size)
    with Session(engine) as db:
        from app.models import User
        user = db.get(User, users["Admin"])
        with pytest.raises(Exception) as error:
            file_services.upload_file(db, user, project["id"], UploadFile(filename="test.pdf", file=Interrupted(pdf_bytes())))
        assert error.value.status_code == 503
    assert not list((root / ".tmp").iterdir())


def test_audit_is_read_only_and_includes_soft_deleted_space(files):
    client, engine, _, project, root = files
    record = upload(client, project).json()
    assert client.delete(f"/api/files/{record['id']}").status_code == 204
    orphan = root / uuid4().hex; orphan.write_bytes(b"orphan"); os.utime(orphan, (1, 1))
    with Session(engine) as db:
        report = audit(db, PrivateStorage(root), verify_checksums=True)
        assert report["retained_deleted_bytes"] == record["size_bytes"]
        assert report["orphans"] == [orphan.name]
        assert report["missing"] == [] and report["mismatched"] == []
    assert orphan.exists()


def test_auth_and_project_access_checked_before_multipart_is_consumed(files):
    client, _, _, project, _ = files
    consumed = []
    def body():
        consumed.append(True)
        yield b"untrusted body"
    login(client, "outsider@example.com")
    assert client.post(f"/api/projects/{project['id']}/files", content=body(), headers={"Content-Type": "multipart/form-data; boundary=test"}).status_code == 403
    assert consumed == []
    client.cookies.clear()
    assert client.post(f"/api/projects/{project['id']}/files", content=body(), headers={"Content-Type": "multipart/form-data; boundary=test"}).status_code == 401
    assert consumed == []


def test_disabled_user_and_real_ten_megabyte_limit(files):
    client, _, users, project, _ = files
    record = upload(client, project).json()
    limit = get_settings().max_upload_bytes
    assert upload(client, project, b"%PDF-" + b"x" * (limit - 4)).status_code == 413
    login(client, "employee@example.com")
    token = client.cookies["workspace_session"]
    client.cookies.clear(); login(client)
    assert client.patch(f"/api/users/{users['Employee']}/status", json={"is_active": False}).status_code == 200
    client.cookies.clear(); client.cookies.set("workspace_session", token)
    assert upload(client, project).status_code == 401
    assert client.get(f"/api/files/{record['id']}/download").status_code == 401


@pytest.mark.parametrize("change", ["archive", "disable"])
def test_permissions_rechecked_after_validation_before_storage_commit(files, monkeypatch, change):
    client, engine, users, project, root = files
    original = file_services.validate_content
    def validate_then_change(path, extension):
        mime = original(path, extension)
        from app.models import Project, User, utcnow
        with Session(engine) as db:
            if change == "archive":
                item = db.get(Project, project["id"]); item.is_archived = True; item.archived_at = utcnow()
            else:
                db.get(User, users["Admin"]).is_active = False
            db.commit()
        return mime
    monkeypatch.setattr(file_services, "validate_content", validate_then_change)
    result = upload(client, project)
    assert result.status_code == (409 if change == "archive" else 401)
    assert not list((root / ".tmp").iterdir())
    with Session(engine) as db: assert db.scalar(select(ProjectFile.id)) is None


def test_multipart_spool_disk_full_closes_handle_and_returns_safe_error(files, monkeypatch, caplog):
    client, engine, _, project, _ = files
    import starlette.formparsers
    handles = []
    class FullDisk(io.BytesIO):
        _rolled = True
        def write(self, data): raise OSError(errno.ENOSPC, "private-spool-path")
    def spool(*args, **kwargs):
        handle = FullDisk(); handles.append(handle); return handle
    monkeypatch.setattr(starlette.formparsers, "SpooledTemporaryFile", spool)
    response = upload(client, project)
    assert response.status_code == 503
    assert handles and all(handle.closed for handle in handles)
    assert "private-spool-path" not in response.text + caplog.text
    with Session(engine) as db: assert db.scalar(select(ProjectFile.id)) is None


@pytest.mark.parametrize("event_name,committed", [("before_commit", False), ("after_commit", True)])
def test_commit_failure_preserves_only_objects_that_may_have_committed(files, event_name, committed):
    client, engine, _, project, root = files
    def fail(db):
        if any(isinstance(row, ProjectFile) for row in db.identity_map.values()):
            raise OperationalError("private SQL", {}, Exception("lost connection"))
    event.listen(Session, event_name, fail)
    try:
        assert upload(client, project).status_code == 503
    finally:
        event.remove(Session, event_name, fail)
    assert not list((root / ".tmp").iterdir())
    with Session(engine) as db:
        row = db.scalar(select(ProjectFile))
        if committed:
            assert row is not None and (root / row.storage_key).exists()
            assert audit(db, PrivateStorage(root), verify_checksums=True)["mismatched"] == []
        else:
            assert row is None and [path for path in root.iterdir() if path.is_file()] == []
