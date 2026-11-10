from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query
from sqlalchemy import select

from . import knowledge_services as service
from .search_service import search
from .knowledge_schemas import (
    ArticleCreate,
    ArticleFilters,
    ArticleOut,
    ArticleUpdate,
    CategoryCreate,
    CategoryFilters,
    CategoryOut,
    CategoryUpdate,
    SearchFilters,
    SearchHit,
)
from .models import ActivityLog, Role
from .security import Admin, CurrentUser, Db
from .work_schemas import Page

router = APIRouter(prefix="/api", tags=["Knowledge & Search"])


@router.get("/knowledge/categories", response_model=Page[CategoryOut])
def categories(filters: Annotated[CategoryFilters, Query()], user: CurrentUser, db: Db):
    return service.list_categories(db, filters)


@router.post("/knowledge/categories", response_model=CategoryOut, status_code=201)
def create_category(payload: CategoryCreate, user: Admin, db: Db):
    return service.save_category(db, user, payload)


@router.get("/knowledge/categories/{identifier}", response_model=CategoryOut)
def category(identifier: UUID, user: CurrentUser, db: Db):
    return service.category(db, identifier)


@router.patch("/knowledge/categories/{identifier}", response_model=CategoryOut)
def update_category(identifier: UUID, payload: CategoryUpdate, user: Admin, db: Db):
    return service.save_category(db, user, payload, identifier)


@router.delete("/knowledge/categories/{identifier}", status_code=204)
def delete_category(identifier: UUID, user: Admin, db: Db):
    service.delete_category(db, identifier)


@router.get("/knowledge/articles", response_model=Page[ArticleOut])
def articles(filters: Annotated[ArticleFilters, Query()], user: CurrentUser, db: Db):
    return service.list_articles(db, user, filters)


@router.post("/knowledge/articles", response_model=ArticleOut, status_code=201)
def create_article(payload: ArticleCreate, user: CurrentUser, db: Db):
    return service.save_article(db, user, payload)


@router.get("/knowledge/articles/{identifier}", response_model=ArticleOut)
def article(identifier: UUID, user: CurrentUser, db: Db):
    return service.article_out(service.get_article(db, identifier, user), user)


@router.patch("/knowledge/articles/{identifier}", response_model=ArticleOut)
def update_article(identifier: UUID, payload: ArticleUpdate, user: CurrentUser, db: Db):
    return service.save_article(db, user, payload, identifier)


@router.post("/knowledge/articles/{identifier}/publish", response_model=ArticleOut)
def publish(identifier: UUID, user: CurrentUser, db: Db):
    return service.transition(db, user, identifier, "publish")


@router.post("/knowledge/articles/{identifier}/archive", response_model=ArticleOut)
def archive(identifier: UUID, user: CurrentUser, db: Db):
    return service.transition(db, user, identifier, "archive")


@router.get("/knowledge/articles/{identifier}/activity")
def activity(identifier: UUID, user: CurrentUser, db: Db):
    row = service.get_article(db, identifier, user)
    if user.role != Role.ADMIN and not (
        user.role == Role.MANAGER and row.project and row.project.manager_id == user.id
    ):
        raise HTTPException(403, "سجل التعديلات متاح لمحرري المقال فقط")
    return [
        dict(
            id=row.id,
            actor_id=row.actor_id,
            action=row.action,
            created_at=row.created_at,
        )
        for row in db.scalars(
            select(ActivityLog)
            .where(ActivityLog.article_id == str(identifier))
            .order_by(ActivityLog.created_at.desc())
            .limit(100)
        )
    ]


@router.get("/search", response_model=Page[SearchHit])
def global_search(
    filters: Annotated[SearchFilters, Query()], user: CurrentUser, db: Db
):
    return search(db, user, filters)
