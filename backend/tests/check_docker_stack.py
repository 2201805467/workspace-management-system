"""Smoke check against local Docker; remove only accounts created by this run."""
import json
import os
import secrets
from http.cookiejar import CookieJar
from urllib.error import HTTPError
from urllib.request import HTTPCookieProcessor, Request, build_opener

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.db import get_engine
from app.models import AccessSession, Role, User
from app.security import password_hasher


def main():
    base_url = os.environ.get("STACK_URL", "http://localhost:8080")
    password = secrets.token_urlsafe(24)
    email = f"smoke-{secrets.token_hex(8)}@example.com"
    ids = []
    opener = build_opener(HTTPCookieProcessor(CookieJar()))

    def request(path, method="GET", data=None):
        encoded = json.dumps(data).encode() if data is not None else None
        req = Request(base_url + path, data=encoded, method=method,
                      headers={"Content-Type": "application/json", "X-Requested-With": "WorkSpace",
                               "Origin": base_url})
        with opener.open(req, timeout=10) as response:
            raw = response.read()
            return response.status, json.loads(raw) if raw else None

    try:
        with Session(get_engine()) as db:
            user = User(name="Temporary smoke test", email=email, role=Role.ADMIN,
                        password_hash=password_hasher.hash(password))
            db.add(user)
            db.commit()
            ids.append(user.id)
        assert request("/api/health")[1]["database"] == "connected"
        assert request("/api/auth/login", "POST", {"email": email, "password": password})[1]["role"] == "Admin"
        assert request("/api/auth/me")[1]["id"] == ids[0]
        status, employee = request("/api/users", "POST", {
            "name": "Temporary employee", "email": "employee-" + email,
            "password": secrets.token_urlsafe(24), "role": "Employee"})
        assert status == 201
        ids.append(employee["id"])
        assert request("/api/auth/logout", "POST")[0] == 204
        try:
            request("/api/auth/me")
            raise AssertionError("Logout did not revoke the session")
        except HTTPError as error:
            assert error.code == 401
        print("Docker stack smoke check passed: Nginx -> FastAPI -> PostgreSQL, login/create/logout.")
    finally:
        if ids:
            with Session(get_engine()) as db:
                db.execute(delete(AccessSession).where(AccessSession.user_id.in_(ids)))
                db.execute(delete(User).where(User.id.in_(ids)))
                db.commit()
        get_engine().dispose()


if __name__ == "__main__":
    main()
