from datetime import datetime, timedelta, timezone

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import reset_admin_password as recovery
from app.db import Base
from app.models import AccessSession, Role, User
from app.security import password_hasher


def test_admin_recovery_retries_revokes_sessions_and_preserves_other_accounts(monkeypatch, capsys):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    old_hash = password_hasher.hash("OldTrainingPassword!123")
    with Session(engine) as db:
        admin = User(name="Taha", email="admin@example.com", role=Role.ADMIN, password_hash=old_hash)
        employee = User(name="Employee", email="employee@example.com", role=Role.EMPLOYEE, password_hash=old_hash)
        db.add_all([admin, employee]); db.flush()
        for person, token in [(admin, "a" * 64), (employee, "b" * 64)]:
            db.add(AccessSession(user_id=person.id, token_hash=token, expires_at=datetime.now(timezone.utc) + timedelta(hours=1)))
        db.commit()
    monkeypatch.setattr(recovery, "get_engine", lambda: engine)
    choices = iter(["99", ""])
    passwords = iter(["short", "short", "MismatchPassword!123", "different", "NewTrainingPassword!123", "NewTrainingPassword!123"])
    monkeypatch.setattr("builtins.input", lambda _: next(choices))
    monkeypatch.setattr(recovery, "getpass", lambda _: next(passwords))
    recovery.main()
    output = capsys.readouterr().out
    assert "admin@example.com" in output and "employee@example.com" not in output
    assert "12 إلى 128" in output and "غير متطابقتين" in output
    assert all(secret not in output for secret in ["short", "MismatchPassword!123", "NewTrainingPassword!123"])
    with Session(engine) as db:
        admin = db.scalar(select(User).where(User.role == Role.ADMIN))
        assert password_hasher.verify("NewTrainingPassword!123", admin.password_hash)
        assert len(db.scalars(select(User)).all()) == 2
        assert db.scalar(select(User).where(User.role == Role.EMPLOYEE)).password_hash == old_hash
        assert [session.token_hash for session in db.scalars(select(AccessSession))] == ["b" * 64]
    engine.dispose()


def test_cancelled_recovery_does_not_change_password(monkeypatch):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    old_hash = password_hasher.hash("OldTrainingPassword!123")
    with Session(engine) as db:
        db.add(User(name="Taha", email="admin@example.com", role=Role.ADMIN, password_hash=old_hash)); db.commit()
    monkeypatch.setattr(recovery, "get_engine", lambda: engine)
    monkeypatch.setattr("builtins.input", lambda _: "")
    def cancel(_): raise KeyboardInterrupt
    monkeypatch.setattr(recovery, "getpass", cancel)
    recovery.main()
    with Session(engine) as db:
        assert db.scalar(select(User)).password_hash == old_hash
    engine.dispose()
