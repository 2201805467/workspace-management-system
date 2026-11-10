from datetime import timedelta
from pathlib import Path
from uuid import uuid4

import pytest
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.models import (
    ActivityLog,
    FileSearchIndex,
    KnowledgeArticle,
    ProjectFile,
    utcnow,
)
from app.index_worker import process_one
from app.config import get_settings
from tests.test_auth import login, setup
from tests.test_work import work
from tests.test_files import files, upload
from tests.file_samples import docx_bytes, pdf_bytes, text_pdf_bytes


def article(client, **values):
    return client.post(
        "/api/knowledge/articles",
        json={
            "title": "دليل إدارة المشاريع",
            "content": "هذا الدليل يشرح استخدام WorkSpace في الشركة.",
            **values,
        },
    )


def test_categories_articles_publication_validation_and_audit(work):
    client, engine, users, project = work
    category = client.post(
        "/api/knowledge/categories", json={"name": "الدعم الفني", "slug": "support"}
    ).json()
    assert (
        client.post(
            "/api/knowledge/categories", json={"name": "تصنيف مكرر", "slug": "support"}
        ).status_code
        == 409
    )
    draft = article(client, category_id=category["id"]).json()
    aid = draft["id"]
    assert draft["status"] == "draft" and draft["can_edit"]
    assert article(client, slug=draft["slug"]).status_code == 409
    assert (
        client.delete(f"/api/knowledge/categories/{category['id']}").status_code == 409
    )
    assert (
        client.patch(
            f"/api/knowledge/categories/{category['id']}",
            json={"description": "مساعدة الموظفين"},
        ).status_code
        == 200
    )
    login(client, "employee@example.com")
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 404
    assert client.get("/api/knowledge/articles?status=all").json()["total"] == 0
    assert article(client).status_code == 403
    assert (
        client.post("/api/knowledge/categories", json={"name": "ممنوع"}).status_code
        == 403
    )
    login(client)
    empty = article(client, title="مقال دون محتوى", content="").json()
    assert (
        client.post(f"/api/knowledge/articles/{empty['id']}/publish").status_code == 400
    )
    published = client.post(f"/api/knowledge/articles/{aid}/publish").json()
    assert published["published_at"] and published["status"] == "published"
    assert (
        client.patch(f"/api/knowledge/articles/{aid}", json={"content": ""}).status_code
        == 400
    )
    assert (
        client.patch(
            f"/api/knowledge/articles/{aid}", json={"project_id": project["id"]}
        ).status_code
        == 422
    )
    assert article(client, title="    ").status_code == 422
    assert article(client, content="x" * 50001).status_code == 422
    assert article(client, category_id=str(uuid4())).status_code == 404
    assert article(client, slug="bad/slug").status_code == 422
    preserved = article(
        client, title="مقال يحفظ تنسيق الكود", content='    print("indented")\n'
    ).json()
    assert preserved["content"] == '    print("indented")\n'
    login(client, "employee@example.com")
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 200
    assert (
        client.patch(
            f"/api/knowledge/articles/{aid}", json={"title": "تغيير ممنوع"}
        ).status_code
        == 403
    )
    login(client)
    assert (
        client.patch(
            f"/api/knowledge/articles/{aid}",
            json={"category_id": None, "summary": "ملخص جديد"},
        ).status_code
        == 200
    )
    assert client.post(f"/api/knowledge/articles/{aid}/archive").json()["archived_at"]
    with Session(engine) as db:
        assert {
            row.action
            for row in db.scalars(
                select(ActivityLog).where(ActivityLog.article_id == aid)
            )
        } >= {"created", "publish", "updated", "archive"}
    login(client, "employee@example.com")
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 404
    assert client.get("/api/knowledge/categories").json()["total"] == 1


def test_project_article_visibility_manager_ownership_and_archive(work):
    client, engine, users, project = work
    login(client, "manager@example.com")
    assert article(client).status_code == 403
    draft = article(client, project_id=project["id"]).json()
    aid = draft["id"]
    assert client.get("/api/knowledge/articles?status=draft").json()["total"] == 1
    assert client.post(f"/api/knowledge/articles/{aid}/publish").status_code == 200
    login(client, "other@example.com")
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 404
    assert (
        client.patch(
            f"/api/knowledge/articles/{aid}", json={"title": "مشروع غير متاح"}
        ).status_code
        == 404
    )
    login(client, "employee@example.com")
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 200
    login(client)
    assert client.delete(f"/api/projects/{project['id']}").status_code == 204
    assert client.get(f"/api/knowledge/articles/{aid}").status_code == 200
    assert (
        client.patch(
            f"/api/knowledge/articles/{aid}", json={"title": "تغيير الأرشيف"}
        ).status_code
        == 409
    )


def test_native_search_normalization_ranking_fuzzy_and_private_counts(work):
    client, engine, users, project = work
    if engine.dialect.name != "postgresql":
        pytest.skip("Native PostgreSQL search")

    def publish(**values):
        response = article(client, **values)
        assert response.status_code == 201, response.text
        row = response.json()
        assert (
            client.post(f"/api/knowledge/articles/{row['id']}/publish").status_code
            == 200
        )
        return row

    primary = publish(
        title="إدارة المشاريع والملفّات",
        content="دليل مسؤول الموارد والعمل على ملفات الشركة.",
    )
    body = publish(
        title="إرشادات الشركة اليومية", content="إدارة المشاريع والملفات في الشركة."
    )
    english = publish(
        title="Employee onboarding handbook",
        language="en",
        content="Employees are running onboarding projects and reviewing documentation.",
    )
    private = publish(
        title="SecretQuasar private guide",
        project_id=project["id"],
        content="SecretQuasar private budget",
    )
    article(client, title="HiddenNebula unpublished draft", content="HiddenNebula")
    assert (
        client.get("/api/search?q=ادارة المشاريع").json()["items"][0]["id"]
        == primary["id"]
    )
    for term in ["مسئول", "علي", "ملفات", "الملفات"]:
        response = client.get("/api/search", params={"q": term})
        assert response.status_code == 200, response.text
        assert primary["id"] in {row["id"] for row in response.json()["items"]}
    for term in ["running", "run", "onboadring"]:
        response = client.get("/api/search", params={"q": term})
        assert response.status_code == 200, response.text
        assert english["id"] in {row["id"] for row in response.json()["items"]}, term
    assert client.get("/api/search?q=HiddenNebula").json()["total"] == 0
    login(client, "outsider@example.com")
    response = client.get("/api/search?q=SecretQuasar").json()
    assert response["total"] == 0 and response["items"] == []
    login(client, "employee@example.com")
    assert client.get("/api/search?q=SecretQuasar").json()["total"] == 1
    login(client)
    assert (
        client.delete(
            f"/api/projects/{project['id']}/members/{users['Employee']}"
        ).status_code
        == 204
    )
    login(client, "employee@example.com")
    assert client.get("/api/search?q=SecretQuasar").json()["total"] == 0
    login(client)
    assert (
        client.patch(
            f"/api/knowledge/articles/{primary['id']}",
            json={"title": "سياسة جديدة مميزة", "content": "UniqueAfterEditToken"},
        ).status_code
        == 200
    )
    assert client.get("/api/search?q=UniqueAfterEditToken").json()["total"] == 1
    assert (
        client.post(f"/api/knowledge/articles/{primary['id']}/archive").status_code
        == 200
    )
    assert client.get("/api/search?q=UniqueAfterEditToken").json()["total"] == 0
    for query in ["", " " * 3, "x" * 201]:
        assert client.get("/api/search", params={"q": query}).status_code == 422
    assert client.get("/api/search?q=test&page_size=101").status_code == 422
    assert client.get("/api/search?q=test&type=invalid").status_code == 422
    assert (
        client.get("/api/search", params={"q": "'; DROP TABLE users; --"}).status_code
        == 200
    )


def test_file_index_extraction_leases_visibility_and_failure(files, monkeypatch):
    client, engine, users, project, root = files
    if engine.dialect.name != "postgresql":
        pytest.skip("Native PostgreSQL index worker")
    document = upload(
        client,
        project,
        docx_bytes({"custom.xml": "<extra>ignored</extra>"}),
        name="كتيب المشروع.docx",
    ).json()
    assert (
        client.get(f"/api/files/{document['id']}/index").json()["indexing_status"]
        == "pending"
    )
    assert process_one(engine)
    assert (
        client.get(f"/api/files/{document['id']}/index").json()["indexing_status"]
        == "ready"
    )
    assert client.get("/api/search?q=Test document&type=file").json()["total"] == 1
    login(client, "outsider@example.com")
    assert client.get("/api/search?q=Test document&type=file").json()["total"] == 0
    login(client)
    assert client.delete(f"/api/files/{document['id']}").status_code == 204
    assert client.get("/api/search?q=Test document&type=file").json()["total"] == 0
    blank = upload(client, project, pdf_bytes(), name="scan.pdf").json()
    assert process_one(engine)
    assert (
        client.get(f"/api/files/{blank['id']}/index").json()["indexing_status"]
        == "ready"
    )
    missing = upload(client, project, name="missing.pdf").json()
    with Session(engine) as db:
        file = db.get(ProjectFile, missing["id"])
        (root / file.storage_key).unlink()
        job = db.scalar(
            select(FileSearchIndex).where(FileSearchIndex.file_id == file.id)
        )
        job.indexing_status = "processing"
        job.updated_at = utcnow() - timedelta(seconds=200)
        job.lease_token = "stale"
        db.commit()
    assert process_one(engine)
    assert (
        client.get(f"/api/files/{missing['id']}/index").json()["error_code"]
        == "missing_file"
    )
    assert (
        client.get("/api/search?q=missing&type=file").json()["total"] == 1
    )  # Name still searchable.
    assert client.post(f"/api/files/{blank['id']}/reindex").status_code == 200
    with Session(engine) as db:
        assert (
            len(
                db.scalars(
                    select(FileSearchIndex).where(
                        FileSearchIndex.file_id == blank["id"]
                    )
                ).all()
            )
            == 1
        )


def test_pdf_text_limits_timeout_retry_and_original_download(files, monkeypatch):
    client, engine, users, project, root = files
    if engine.dialect.name != "postgresql":
        pytest.skip("Native PostgreSQL index worker")
    row = upload(client, project, text_pdf_bytes(), name="handbook.pdf").json()
    assert process_one(engine)
    assert (
        client.get("/api/search?q=SearchablePdfNeedle&type=file").json()["total"] == 1
    )
    from app import index_worker
    import subprocess

    original = index_worker.subprocess.run

    def timeout(*args, **kwargs):
        raise subprocess.TimeoutExpired("extract", 1)

    assert client.post(f"/api/files/{row['id']}/reindex").status_code == 200
    monkeypatch.setattr(index_worker.subprocess, "run", timeout)
    assert process_one(engine)
    assert client.get(f"/api/files/{row['id']}/index").json()["error_code"] == "timeout"
    assert client.get(f"/api/files/{row['id']}/download").status_code == 200
    monkeypatch.setattr(index_worker.subprocess, "run", original)
    assert client.post(f"/api/files/{row['id']}/reindex").status_code == 200
    monkeypatch.setattr(get_settings(), "index_max_text_chars", 10)
    assert process_one(engine)
    with Session(engine) as db:
        job = db.scalar(
            select(FileSearchIndex).where(FileSearchIndex.file_id == row["id"])
        )
        assert len(job.extracted_text) <= 10 and job.indexing_status == "ready"


def test_combined_search_filters_pages_and_transaction_rollback(work, monkeypatch):
    client, engine, users, project = work
    if engine.dialect.name != "postgresql":
        pytest.skip("Native PostgreSQL search")
    category = client.post(
        "/api/knowledge/categories", json={"name": "اختبارات البحث"}
    ).json()
    ids = []
    for i in range(4):
        row = article(
            client,
            title=f"دليل دليل الموظفين {i}",
            category_id=category["id"],
            project_id=project["id"],
            language="ar",
        ).json()
        ids.append(row["id"])
        assert (
            client.post(f"/api/knowledge/articles/{row['id']}/publish").status_code
            == 200
        )
    params = dict(
        q="الموظفين",
        type="article",
        category_id=category["id"],
        project_id=project["id"],
        language="ar",
        sort="title",
        page_size=2,
    )
    result = client.get("/api/search", params=params).json()
    assert (
        result["total"] == 4
        and result["total_pages"] == 2
        and len(result["items"]) == 2
    )
    second = client.get("/api/search", params={**params, "page": 2}).json()
    assert not {row["id"] for row in result["items"]} & {
        row["id"] for row in second["items"]
    }
    assert (
        client.get(
            "/api/search", params={**params, "updated_from": "2090-01-01"}
        ).json()["total"]
        == 0
    )
    from sqlalchemy import event
    from sqlalchemy.exc import OperationalError

    def fail(db, context, instances):
        if any(isinstance(row, KnowledgeArticle) for row in db.dirty):
            raise OperationalError("hidden SQL", {}, Exception("failure"))

    event.listen(Session, "before_flush", fail)
    try:
        assert (
            client.patch(
                f"/api/knowledge/articles/{ids[0]}",
                json={"content": "ShouldNotPersistUniqueToken"},
            ).status_code
            == 503
        )
    finally:
        event.remove(Session, "before_flush", fail)
    assert client.get("/api/search?q=ShouldNotPersistUniqueToken").json()["total"] == 0
    assert client.get("/api/search", params=params).json()["total"] == 4
