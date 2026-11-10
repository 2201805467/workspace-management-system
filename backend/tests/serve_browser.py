"""Isolated loopback-only server for browser tests. Never uses the app database."""
import os
from pathlib import Path
from tempfile import TemporaryDirectory


def main():
    with TemporaryDirectory(prefix="workspace-browser-") as directory:
        browser_url=os.environ.get('BROWSER_TEST_DATABASE_URL')
        os.environ["DATABASE_URL"] = browser_url or "sqlite:///" + (Path(directory) / "test.sqlite").as_posix()
        os.environ["ALLOWED_ORIGINS"] = '["http://localhost:5174"]'
        os.environ["COOKIE_SECURE"] = "false"
        os.environ["FILE_STORAGE_PATH"] = str(Path(directory) / "files")

        import uvicorn
        from sqlalchemy.orm import Session
        from app.db import Base, get_engine
        from app.models import Role, User
        from app.security import password_hasher

        if browser_url:
            if not get_engine().url.database.endswith('_browser_test'):
                raise SystemExit('Use a dedicated *_browser_test database, never the application database.')
            # This explicitly disposable database may contain a previous browser
            # run interrupted by the OS. Drop only its known application tables.
            Base.metadata.drop_all(get_engine())
            from sqlalchemy import text
            with get_engine().begin() as connection: connection.execute(text('DROP TABLE IF EXISTS alembic_version'))
            from alembic import command
            from alembic.config import Config
            command.upgrade(Config('alembic.ini'),'head')
        else: Base.metadata.create_all(get_engine())
        with Session(get_engine()) as db:
            db.add(User(name="مسؤول الاختبار", email="admin@example.com", role=Role.ADMIN,
                        password_hash=password_hasher.hash("BrowserTestOnly!123")))
            db.commit()
        uvicorn.run("app.main:app", host="127.0.0.1", port=8001, log_level="warning")
        get_engine().dispose()


if __name__ == "__main__":
    main()
