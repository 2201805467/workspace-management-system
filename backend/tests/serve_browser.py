"""Isolated loopback-only server for browser tests. Never uses the app database."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="workspace-browser-") as directory:
        os.environ["DATABASE_URL"] = "sqlite:///" + (Path(directory) / "test.sqlite").as_posix()
        os.environ["ALLOWED_ORIGINS"] = '["http://localhost:5174"]'
        os.environ["COOKIE_SECURE"] = "false"

        import uvicorn
        from sqlalchemy.orm import Session
        from app.db import Base, get_engine
        from app.models import Role, User
        from app.security import password_hasher

        Base.metadata.create_all(get_engine())
        with Session(get_engine()) as db:
            db.add(User(name="مسؤول الاختبار", email="admin@example.com", role=Role.ADMIN,
                        password_hash=password_hasher.hash("BrowserTestOnly!123")))
            db.commit()
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
        get_engine().dispose()


if __name__ == "__main__":
    main()
