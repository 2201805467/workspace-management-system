import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app import bootstrap
from app.db import Base
from app.models import Role, User
from app.security import password_hasher


@pytest.mark.parametrize("email,password,confirmation,expected", [
    ("admin@example.com", "short123", "short123", "12 إلى 128"),
    ("invalid-email", "LongTestPassword!123", "LongTestPassword!123", "بريدًا إلكترونيًا صحيحًا"),
    ("admin@example.com", "LongTestPassword!123", "different", "غير متطابقتين"),
])
def test_bootstrap_retries_without_exposing_secrets(monkeypatch, capsys, email, password, confirmation, expected):
    engine = create_engine("sqlite://")
    Base.metadata.create_all(engine)
    monkeypatch.setattr(bootstrap, "get_engine", lambda: engine)
    inputs = iter(["Taha", email, "Taha", "ADMIN@example.com"])
    secrets = iter([password, confirmation, "ValidTrainingPassword!123", "ValidTrainingPassword!123"])
    monkeypatch.setattr("builtins.input", lambda _: next(inputs))
    monkeypatch.setattr(bootstrap, "getpass", lambda _: next(secrets))

    bootstrap.main()

    output = capsys.readouterr().out
    assert expected in output
    assert "تم إنشاء حساب المسؤول" in output
    assert password not in output and confirmation not in output
    assert "ValidTrainingPassword!123" not in output
    assert "Traceback" not in output and "input_value" not in output
    with Session(engine) as db:
        users = db.scalars(select(User)).all()
        assert len(users) == 1
        assert users[0].role == Role.ADMIN
        assert users[0].email == "admin@example.com"
        assert password_hasher.verify("ValidTrainingPassword!123", users[0].password_hash)
    engine.dispose()
