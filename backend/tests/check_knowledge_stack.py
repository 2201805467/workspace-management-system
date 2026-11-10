"""Temporary Docker integration probe. IDs only are saved; no credentials."""

import argparse, json, secrets, time
from pathlib import Path
from urllib.parse import urlencode
import subprocess
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from app.db import get_engine
from app.models import (
    AccessSession,
    ActivityLog,
    KnowledgeArticle,
    KnowledgeCategory,
    Project,
    ProjectFile,
    ProjectMember,
    Role,
    User,
)
from app.security import password_hasher
from tests.check_files_stack import Client, ROOT
from tests.file_samples import docx_bytes

PROBE = ROOT / "backend" / ".tmp" / "phase04-probe.json"
NEEDLE = "PersistentKnowledgeNeedle"


def credentials(ids):
    password = secrets.token_urlsafe(24)
    with Session(get_engine()) as db:
        user = db.get(User, ids["user"])
        assert user and user.email.startswith("phase04-")
        user.password_hash = password_hasher.hash(password)
        email = user.email
        db.commit()
    client = Client()
    client.request("/api/auth/login", "POST", dict(email=email, password=password))
    return client


def prepare():
    if PROBE.exists():
        raise SystemExit("Existing probe must be cleaned first.")
    ids = {
        "user": None,
        "category": None,
        "project": None,
        "article": None,
        "file": None,
    }
    PROBE.parent.mkdir(exist_ok=True)

    def save():
        PROBE.write_text(json.dumps(ids), encoding="utf-8")

    with Session(get_engine()) as db:
        user = User(
            name="Temporary knowledge probe",
            email=f"phase04-{secrets.token_hex(8)}@example.com",
            role=Role.ADMIN,
            password_hash=password_hasher.hash(secrets.token_urlsafe(24)),
        )
        db.add(user)
        db.commit()
        ids["user"] = user.id
        save()
    client = credentials(ids)
    category = client.request(
        "/api/knowledge/categories", "POST", dict(name="Temporary knowledge category")
    )
    ids["category"] = category["id"]
    save()
    project = client.request(
        "/api/projects",
        "POST",
        dict(name="Temporary knowledge project", manager_id=ids["user"]),
    )
    ids["project"] = project["id"]
    save()
    article = client.request(
        "/api/knowledge/articles",
        "POST",
        dict(
            title="Temporary knowledge guide",
            content=NEEDLE,
            project_id=project["id"],
            category_id=category["id"],
        ),
    )
    ids["article"] = article["id"]
    save()
    client.request(f"/api/knowledge/articles/{article['id']}/publish", "POST")
    boundary = secrets.token_hex(16)
    data = docx_bytes(text=NEEDLE + " document text")
    body = (
        (
            f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="probe.docx"\r\nContent-Type: application/vnd.openxmlformats-officedocument.wordprocessingml.document\r\n\r\n'
        ).encode()
        + data
        + f"\r\n--{boundary}--\r\n".encode()
    )
    file = client.request(
        f"/api/projects/{project['id']}/files",
        "POST",
        body,
        content_type=f"multipart/form-data; boundary={boundary}",
    )
    ids["file"] = file["id"]
    save()
    assert (
        client.request(f"/api/files/{file['id']}/index")["indexing_status"] == "pending"
    )
    client.request("/api/auth/logout", "POST")
    print("Published article and durable pending DOCX job prepared.")


def verify():
    ids = json.loads(PROBE.read_text())
    client = credentials(ids)
    deadline = time.monotonic() + 45
    while True:
        status = client.request(f"/api/files/{ids['file']}/index")
        if status["indexing_status"] == "ready":
            break
        if status["indexing_status"] == "failed" or time.monotonic() > deadline:
            raise AssertionError(status)
        time.sleep(0.5)
    result = client.request("/api/search?" + urlencode({"q": NEEDLE}))
    assert {("article", ids["article"]), ("file", ids["file"])} <= {
        (row["type"], row["id"]) for row in result["items"]
    }
    client.request("/api/auth/logout", "POST")
    print(
        "Docker worker resumed pending job; persisted article and DOCX content are searchable."
    )


def cleanup():
    ids = json.loads(PROBE.read_text())
    with Session(get_engine()) as db:
        user = db.get(User, ids["user"])
        assert user and user.email.startswith("phase04-")
        if ids["file"]:
            file = db.get(ProjectFile, ids["file"])
            if file:
                code = "import sys;from app.file_storage import PrivateStorage;PrivateStorage().path(sys.argv[1]).unlink(missing_ok=True)"
                subprocess.run(
                    [
                        "docker",
                        "compose",
                        "exec",
                        "-T",
                        "backend",
                        "python",
                        "-c",
                        code,
                        file.storage_key,
                    ],
                    cwd=ROOT,
                    check=True,
                )
                db.delete(file)
                db.flush()
        if ids["article"]:
            db.execute(
                delete(ActivityLog).where(ActivityLog.article_id == ids["article"])
            )
            db.execute(
                delete(KnowledgeArticle).where(KnowledgeArticle.id == ids["article"])
            )
        if ids["category"]:
            db.execute(
                delete(KnowledgeCategory).where(KnowledgeCategory.id == ids["category"])
            )
        if ids["project"]:
            db.execute(
                delete(ProjectMember).where(ProjectMember.project_id == ids["project"])
            )
            db.execute(delete(Project).where(Project.id == ids["project"]))
        db.execute(delete(AccessSession).where(AccessSession.user_id == ids["user"]))
        db.delete(user)
        db.commit()
    PROBE.unlink()
    print("Only temporary knowledge probe data removed.")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("action", choices=["prepare", "verify", "cleanup"])
    args = parser.parse_args()
    try:
        {"prepare": prepare, "verify": verify, "cleanup": cleanup}[args.action]()
    finally:
        get_engine().dispose()
