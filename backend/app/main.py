import secrets
import threading
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from typing import Annotated

from fastapi import Depends, FastAPI, Header, HTTPException, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from sqlalchemy import delete, select, text
from sqlalchemy.exc import IntegrityError

from .config import get_settings
from .models import AccessSession, User
from .schemas import Login, PasswordChange, PasswordReset, UserCreate, UserOut, UserStatus
from .security import Admin, COOKIE_NAME, CurrentUser, Db, dummy_hash, hash_token, password_hasher


def check_csrf(request: Request, x_requested_with: Annotated[str | None, Header()] = None):
    if request.method in {"POST", "PATCH", "PUT", "DELETE"}:
        if x_requested_with != "WorkSpace":
            raise HTTPException(403, "طلب غير مسموح")
        origin = request.headers.get("origin")
        if origin and origin not in get_settings().allowed_origins:
            raise HTTPException(403, "مصدر الطلب غير مسموح")


app = FastAPI(title="WorkSpace API", version="0.1.0", dependencies=[Depends(check_csrf)])


@app.exception_handler(RequestValidationError)
async def validation_error(request: Request, error: RequestValidationError):
    # FastAPI's default validation response can echo submitted passwords.
    safe_errors = [{"loc": item["loc"], "msg": item["msg"], "type": item["type"]}
                   for item in error.errors()]
    return JSONResponse(status_code=422, content={"detail": safe_errors})


# Single-process limiter for this local MVP. Do not trust forwarded IP headers.
login_attempts: dict[str, deque] = defaultdict(deque)
attempts_lock = threading.Lock()


@app.middleware("http")
async def security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    response.headers["X-Content-Type-Options"] = "nosniff"
    return response


@app.get("/api/health")
def health(db: Db):
    db.execute(text("SELECT 1"))
    return {"status": "ok", "database": "connected"}


@app.post("/api/auth/login", response_model=UserOut)
def login(payload: Login, request: Request, response: Response, db: Db):
    key = f"{request.client.host if request.client else 'local'}:{payload.email}"
    now = time.monotonic()
    with attempts_lock:
        # Prune inactive keys so the limiter's memory stays bounded.
        for ip in list(login_attempts):
            while login_attempts[ip] and login_attempts[ip][0] <= now - 60:
                login_attempts[ip].popleft()
            if not login_attempts[ip]:
                del login_attempts[ip]
        attempts = login_attempts[key]
        if len(attempts) >= 10:
            raise HTTPException(429, "محاولات كثيرة. أعد المحاولة بعد دقيقة.", headers={"Retry-After": "60"})
        attempts.append(now)
    user = db.scalar(select(User).where(User.email == payload.email))
    valid = password_hasher.verify(payload.password.get_secret_value(), user.password_hash if user else dummy_hash)
    if not user or not valid or not user.is_active:
        raise HTTPException(401, "البريد الإلكتروني أو كلمة المرور غير صحيحة")
    settings = get_settings()
    token = secrets.token_urlsafe(32)
    old_token = request.cookies.get(COOKIE_NAME)
    if old_token:
        db.execute(delete(AccessSession).where(AccessSession.token_hash == hash_token(old_token)))
    db.execute(delete(AccessSession).where(AccessSession.expires_at <= datetime.now(timezone.utc)))
    db.add(AccessSession(token_hash=hash_token(token), user_id=user.id,
                         expires_at=datetime.now(timezone.utc) + timedelta(hours=settings.session_hours)))
    db.commit()
    response.set_cookie(COOKIE_NAME, token, httponly=True, secure=settings.cookie_secure,
                        samesite="strict", max_age=settings.session_hours * 3600, path="/api")
    return user


@app.get("/api/auth/me", response_model=UserOut)
def me(user: CurrentUser):
    return user


@app.post("/api/auth/logout", status_code=204)
def logout(request: Request, response: Response, db: Db):
    token = request.cookies.get(COOKIE_NAME)
    if token:
        db.execute(delete(AccessSession).where(AccessSession.token_hash == hash_token(token)))
        db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api", secure=get_settings().cookie_secure,
                           httponly=True, samesite="strict")


@app.post("/api/auth/change-password", status_code=204)
def change_password(payload: PasswordChange, user: CurrentUser, db: Db, response: Response):
    if not password_hasher.verify(payload.current_password.get_secret_value(), user.password_hash):
        raise HTTPException(400, "كلمة المرور الحالية غير صحيحة")
    user.password_hash = password_hasher.hash(payload.new_password.get_secret_value())
    db.execute(delete(AccessSession).where(AccessSession.user_id == user.id))
    db.commit()
    response.delete_cookie(COOKIE_NAME, path="/api", secure=get_settings().cookie_secure,
                           httponly=True, samesite="strict")


@app.get("/api/users", response_model=list[UserOut])
def users(admin: Admin, db: Db):
    return db.scalars(select(User).order_by(User.created_at)).all()


@app.post("/api/users", response_model=UserOut, status_code=201)
def create_user(payload: UserCreate, admin: Admin, db: Db):
    user = User(name=payload.name, email=payload.email, role=payload.role,
                password_hash=password_hasher.hash(payload.password.get_secret_value()))
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(409, "البريد الإلكتروني مستخدم بالفعل")
    db.refresh(user)
    return user


@app.patch("/api/users/{user_id}/status", response_model=UserOut)
def set_status(user_id: str, payload: UserStatus, admin: Admin, db: Db):
    if user_id == admin.id:
        raise HTTPException(400, "لا يمكنك تعطيل حسابك الحالي")
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "المستخدم غير موجود")
    user.is_active = payload.is_active
    if not user.is_active:
        db.execute(delete(AccessSession).where(AccessSession.user_id == user.id))
    db.commit()
    return user


@app.post("/api/users/{user_id}/reset-password", status_code=204)
def reset_password(user_id: str, payload: PasswordReset, admin: Admin, db: Db):
    user = db.get(User, user_id)
    if not user:
        raise HTTPException(404, "المستخدم غير موجود")
    user.password_hash = password_hasher.hash(payload.new_password.get_secret_value())
    db.execute(delete(AccessSession).where(AccessSession.user_id == user.id))
    db.commit()
