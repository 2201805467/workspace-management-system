from functools import lru_cache

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session

from .config import get_settings


class Base(DeclarativeBase):
    pass


@lru_cache
def get_engine():
    url = get_settings().database_url
    connect_args = {"connect_timeout": 5} if url.startswith("postgresql") else {}
    return create_engine(url, pool_pre_ping=True, hide_parameters=True, connect_args=connect_args)


def get_db():
    with Session(get_engine()) as db:
        yield db
