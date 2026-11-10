"""Temporary live-stack probe for restart/recreate/backup checks. No credentials saved."""
import argparse
import hashlib
import json
from http.cookiejar import CookieJar
from pathlib import Path
import secrets
import subprocess
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import AccessSession, Project, ProjectFile, ProjectMember, Role, User
from app.security import password_hasher
from tests.file_samples import image_bytes

ROOT = Path(__file__).resolve().parents[2]
PROBE = ROOT / "backend" / ".tmp" / "phase03-probe.json"
BASE = "http://localhost:8080"


class Client:
    def __init__(self): self.opener = build_opener(HTTPCookieProcessor(CookieJar()))
    def request(self, path, method="GET", data=None, *, raw=False, content_type="application/json"):
        encoded = data if isinstance(data, bytes) else json.dumps(data).encode() if data is not None else None
        request = Request(BASE + path, method=method, data=encoded,
                          headers={"Content-Type": content_type, "X-Requested-With": "WorkSpace", "Origin": BASE})
        with self.opener.open(request, timeout=15) as response:
            body = response.read()
            return body if raw else json.loads(body) if body else None
    def upload(self, project_id):
        data = image_bytes(); boundary = secrets.token_hex(16)
        payload = (f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="persistence.png"\r\nContent-Type: image/png\r\n\r\n').encode() + data + f"\r\n--{boundary}--\r\n".encode()
        row = self.request(f"/api/projects/{project_id}/files", "POST", payload, content_type=f"multipart/form-data; boundary={boundary}")
        assert row["checksum"] == hashlib.sha256(data).hexdigest()
        return {"id": row["id"], "checksum": row["checksum"]}


def prepare():
    if PROBE.exists(): raise SystemExit("Existing probe found; verify or clean it first.")
    ids = {"user": None, "project": None, "files": []}
    PROBE.parent.mkdir(exist_ok=True)
    def save(): PROBE.write_text(json.dumps(ids), encoding="utf-8")
    password = secrets.token_urlsafe(24)
    with Session(get_engine()) as db:
        user = User(name="Temporary file probe", email=f"phase03-{secrets.token_hex(8)}@example.com", role=Role.ADMIN, password_hash=password_hasher.hash(password))
        db.add(user); db.commit(); ids["user"] = user.id; email = user.email; save()
    client = Client(); client.request("/api/auth/login", "POST", {"email": email, "password": password})
    project = client.request("/api/projects", "POST", {"name": "Temporary file persistence probe", "manager_id": ids["user"]})
    ids["project"] = project["id"]; save()
    for _ in range(2): ids["files"].append(client.upload(project["id"])); save()
    client.request(f"/api/files/{ids['files'][1]['id']}", "DELETE")
    client.request("/api/auth/logout", "POST")
    print("File probe prepared: one active file and one retained soft-deleted object.")


def verify():
    ids = json.loads(PROBE.read_text())
    password = secrets.token_urlsafe(24)
    with Session(get_engine()) as db:
        user = db.get(User, ids["user"])
        assert user and user.email.startswith("phase03-")
        email = user.email; user.password_hash = password_hasher.hash(password); db.commit()
    client = Client(); client.request("/api/auth/login", "POST", {"email": email, "password": password})
    data = client.request(f"/api/files/{ids['files'][0]['id']}/download", raw=True)
    assert hashlib.sha256(data).hexdigest() == ids["files"][0]["checksum"]
    listing = client.request(f"/api/projects/{ids['project']}/files")
    assert listing["total"] == 1
    try:
        client.request(f"/api/files/{ids['files'][1]['id']}/download", raw=True)
        raise AssertionError("Deleted object was downloadable")
    except HTTPError as error: assert error.code == 404
    client.request("/api/auth/logout", "POST")
    print("File contents and metadata survived; SHA-256 matches and deleted file stays unavailable.")


def cleanup():
    ids = json.loads(PROBE.read_text())
    with Session(get_engine()) as db:
        user = db.get(User, ids["user"])
        assert user and user.email.startswith("phase03-")
        keys = db.scalars(select(ProjectFile.storage_key).where(ProjectFile.project_id == ids["project"], ProjectFile.uploaded_by == user.id)).all()
        code = "import sys,json; from app.file_storage import PrivateStorage; s=PrivateStorage(); [s.path(k).unlink(missing_ok=True) for k in json.load(sys.stdin)]"
        subprocess.run(["docker", "compose", "exec", "-T", "backend", "python", "-c", code], input=json.dumps(keys), text=True, check=True, cwd=ROOT)
        db.execute(delete(ProjectFile).where(ProjectFile.project_id == ids["project"]))
        db.execute(delete(ProjectMember).where(ProjectMember.project_id == ids["project"]))
        db.execute(delete(Project).where(Project.id == ids["project"]))
        db.execute(delete(AccessSession).where(AccessSession.user_id == user.id))
        db.delete(user); db.commit()
    PROBE.unlink()
    print("Only this probe's records and stored objects were removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(); parser.add_argument("action", choices=["prepare", "verify", "cleanup"])
    args = parser.parse_args()
    try: {"prepare": prepare, "verify": verify, "cleanup": cleanup}[args.action]()
    finally: get_engine().dispose()
