import os
from datetime import datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

os.environ.setdefault("DATABASE_URL", "sqlite://")

from app.db import Base, get_db
from app.main import app, login_attempts
from app.models import AccessSession, Role, User
from app.security import COOKIE_NAME, hash_token, password_hasher

PASSWORD = "TrainingPassword!123"
HEADERS = {"X-Requested-With": "WorkSpace", "Origin": "http://localhost:5173"}


@pytest.fixture
def setup():
    # Set TEST_DATABASE_URL to a dedicated, disposable PostgreSQL database to
    # run the same suite against PostgreSQL. Never point this at real data.
    url = os.environ.get("TEST_DATABASE_URL", "sqlite://")
    kwargs = {"connect_args": {"check_same_thread": False}, "poolclass": StaticPool} if url == "sqlite://" else {}
    engine = create_engine(url, **kwargs)
    Base.metadata.create_all(engine)
    with Session(engine) as db:
        db.add_all([User(name="المسؤول", email="admin@example.com", role=Role.ADMIN, password_hash=password_hasher.hash(PASSWORD)),
                    User(name="الموظف", email="employee@example.com", role=Role.EMPLOYEE, password_hash=password_hasher.hash(PASSWORD)),
                    User(name="المدير", email="manager@example.com", role=Role.MANAGER, password_hash=password_hasher.hash(PASSWORD))])
        db.commit()

    def override():
        with Session(engine) as db:
            yield db

    app.dependency_overrides[get_db] = override
    login_attempts.clear()
    with TestClient(app, headers=HEADERS) as client:
        yield client, engine
    app.dependency_overrides.clear()
    Base.metadata.drop_all(engine)
    engine.dispose()


def login(client, email="admin@example.com", password=PASSWORD):
    return client.post("/api/auth/login", json={"email": email, "password": password})


def test_login_cookie_and_logout_revocation(setup):
    client, engine = setup
    assert client.get("/api/health").json()["database"] == "connected"
    assert client.get("/api/auth/me").status_code == 401
    response = login(client)
    assert response.status_code == 200
    assert "password_hash" not in response.json()
    cookie = response.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=strict" in cookie and "path=/api" in cookie
    token = client.cookies[COOKIE_NAME]
    with Session(engine) as db:
        session = db.scalar(select(AccessSession))
        assert session.token_hash == hash_token(token) and session.token_hash != token
    assert client.get("/api/auth/me").json()["role"] == "Admin"
    assert client.post("/api/auth/logout").status_code == 204
    client.cookies.set(COOKIE_NAME, token)
    assert client.get("/api/auth/me").status_code == 401


@pytest.mark.parametrize("email", ["employee@example.com", "manager@example.com"])
def test_roles_cannot_manage_accounts(setup, email):
    client, _ = setup
    assert login(client, email).status_code == 200
    assert client.get("/api/users").status_code == 403
    assert client.post("/api/users", json={"name": "موظف جديد", "email": "new@example.com", "password": PASSWORD}).status_code == 403
    assert client.patch("/api/users/missing/status", json={"is_active": False}).status_code == 403
    assert client.post("/api/users/missing/reset-password", json={"new_password": PASSWORD}).status_code == 403


def test_create_validation_and_duplicate_email(setup):
    client, _ = setup
    login(client)
    data = {"name": "موظف جديد", "email": "NEW@example.com", "password": PASSWORD, "role": "Employee"}
    created = client.post("/api/users", json=data)
    assert created.status_code == 201
    assert created.json()["email"] == "new@example.com"
    assert client.post("/api/users", json=data).status_code == 409
    invalid = client.post("/api/users", json={**data, "password": "short"})
    assert invalid.status_code == 422
    assert '"short"' not in invalid.text and '"input"' not in invalid.text
    assert client.post("/api/users", json={**data, "role": "Owner"}).status_code == 422
    assert client.post("/api/auth/register", json=data).status_code == 404


def test_disable_revokes_sessions_even_after_reactivation(setup):
    client, _ = setup
    login(client, "employee@example.com")
    employee = client.get("/api/auth/me").json()
    old_token = client.cookies[COOKIE_NAME]
    client.cookies.clear()  # Keep the employee session open on another device.
    login(client)
    own_id = client.get("/api/auth/me").json()["id"]
    assert client.patch(f"/api/users/{own_id}/status", json={"is_active": False}).status_code == 400
    assert client.patch(f"/api/users/{employee['id']}/status", json={"is_active": False}).status_code == 200
    assert login(client, employee["email"]).status_code == 401
    assert client.patch(f"/api/users/{employee['id']}/status", json={"is_active": True}).status_code == 200
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, old_token)
    assert client.get("/api/auth/me").status_code == 401


def test_password_change_and_reset_revoke_all_sessions(setup):
    client, _ = setup
    login(client, "employee@example.com")
    employee_id = client.get("/api/auth/me").json()["id"]
    new_password = "ChangedPassword!123"
    assert client.post("/api/auth/change-password", json={"current_password": "wrong", "new_password": new_password}).status_code == 400
    assert client.post("/api/auth/change-password", json={"current_password": PASSWORD, "new_password": new_password}).status_code == 204
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, "employee@example.com").status_code == 401
    assert login(client, "employee@example.com", new_password).status_code == 200
    old_token = client.cookies[COOKIE_NAME]
    client.cookies.clear()
    login(client)
    assert client.post(f"/api/users/{employee_id}/reset-password", json={"new_password": PASSWORD}).status_code == 204
    client.cookies.clear()
    client.cookies.set(COOKIE_NAME, old_token)
    assert client.get("/api/auth/me").status_code == 401
    assert login(client, "employee@example.com").status_code == 200


def test_forged_and_expired_tokens(setup):
    client, engine = setup
    client.cookies.set(COOKIE_NAME, "forged-token")
    assert client.get("/api/auth/me").status_code == 401
    client.cookies.clear()
    login(client)
    with Session(engine) as db:
        session = db.scalar(select(AccessSession))
        session.expires_at = datetime.now(timezone.utc) - timedelta(seconds=1)
        db.commit()
    assert client.get("/api/auth/me").status_code == 401


def test_csrf_and_login_throttling(setup):
    client, _ = setup
    payload = {"email": "admin@example.com", "password": PASSWORD}
    assert client.post("/api/auth/login", json=payload, headers={"X-Requested-With": ""}).status_code == 403
    assert client.post("/api/auth/login", json=payload, headers={"Origin": "https://other.example"}).status_code == 403
    for _ in range(10):
        assert login(client, password="incorrect").status_code == 401
    response = login(client)
    assert response.status_code == 429 and response.headers["retry-after"] == "60"
