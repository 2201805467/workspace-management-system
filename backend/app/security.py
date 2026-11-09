import hashlib
from datetime import datetime, timezone
from typing import Annotated

from fastapi import Cookie, Depends, HTTPException
from pwdlib import PasswordHash
from sqlalchemy.orm import Session

from .db import get_db
from .models import AccessSession, Role, User

password_hasher = PasswordHash.recommended()
dummy_hash = password_hasher.hash("unused-constant-for-timing-check")
COOKIE_NAME = "workspace_session"
Db = Annotated[Session, Depends(get_db)]


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


def current_user(db: Db, workspace_session: Annotated[str | None, Cookie()] = None) -> User:
    session = db.get(AccessSession, hash_token(workspace_session)) if workspace_session else None
    if session:
        expires = session.expires_at
        if expires.tzinfo is None:  # SQLite test databases return naive datetimes.
            expires = expires.replace(tzinfo=timezone.utc)
        user = db.get(User, session.user_id)
        if expires > datetime.now(timezone.utc) and user and user.is_active:
            return user
    raise HTTPException(status_code=401, detail="الجلسة غير صالحة أو انتهت. يرجى تسجيل الدخول.")


CurrentUser = Annotated[User, Depends(current_user)]


def require_admin(user: CurrentUser) -> User:
    if user.role != Role.ADMIN:
        raise HTTPException(status_code=403, detail="هذه العملية متاحة للمسؤول فقط")
    return user


Admin = Annotated[User, Depends(require_admin)]
