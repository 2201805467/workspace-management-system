"""Read-only operational/restore verification; no content or filenames printed."""

import argparse
import json
from sqlalchemy import inspect, text
from .db import get_engine


def check():
    engine = get_engine()
    if not inspect(engine).has_table("knowledge_articles"):
        return {"status": "not_installed"}
    with engine.connect() as db:
        db.execute(
            text(
                "SELECT websearch_to_tsquery('public.workspace_arabic',workspace_normalize('إدارة الملفات'))"
            )
        )
        missing = db.execute(
            text("SELECT count(*) FROM knowledge_articles WHERE search_vector IS NULL")
        ).scalar()
        queued = db.execute(
            text(
                "SELECT count(*) FROM files f LEFT JOIN file_search_index i ON i.file_id=f.id WHERE f.deleted_at IS NULL AND i.id IS NULL"
            )
        ).scalar()
        report = {
            "status": "ok",
            "articles": db.execute(
                text("SELECT count(*) FROM knowledge_articles")
            ).scalar(),
            "file_indexes": db.execute(
                text("SELECT count(*) FROM file_search_index")
            ).scalar(),
            "missing_article_vectors": missing,
            "missing_file_jobs": queued,
        }
        if missing or queued:
            raise RuntimeError("Search integrity check failed")
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--check", action="store_true")
    parser.parse_args()
    try:
        print(json.dumps(check()))
    finally:
        get_engine().dispose()
