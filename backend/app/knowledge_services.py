import re
import unicodedata
from datetime import datetime, time, timedelta
from uuid import uuid4

from fastapi import HTTPException
from sqlalchemy import and_, or_, select
from sqlalchemy.orm import joinedload
from sqlalchemy.exc import IntegrityError

from .models import (
    ActivityLog,
    KnowledgeArticle as Article,
    KnowledgeCategory as Category,
    Project,
    Role,
    utcnow,
)
from .work_repository import paginate, visible_projects
from .work_services import get_project, COMPANY_TZ
from .knowledge_schemas import ArticleOut, CategoryOut


def commit(db):
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "المعرف النصي مستخدم أو السجل مرتبط بمقالات. تحقق من البيانات."
        ) from None


def slugify(value, fallback):
    slug = re.sub(r"[\W_]+", "-", unicodedata.normalize("NFC", value).lower()).strip(
        "-"
    )[:190]
    return slug if len(slug) >= 3 else fallback + "-" + uuid4().hex[:8]


def valid_slug(value):
    if not re.fullmatch(r"[^\W_]+(?:-[^\W_]+)*", value):
        raise HTTPException(
            422, "المعرف النصي يقبل الحروف والأرقام والشرطة بين الكلمات فقط"
        )
    return value.lower()


def category(db, identifier):
    row = db.get(Category, str(identifier))
    if row is None:
        raise HTTPException(404, "التصنيف غير موجود")
    return row


def save_category(db, user, payload, identifier=None):
    data = payload.model_dump(exclude_unset=True)
    row = category(db, identifier) if identifier else Category(created_by=user.id)
    if "slug" in data and data["slug"] is not None:
        data["slug"] = valid_slug(data["slug"])
    elif not identifier:
        data["slug"] = slugify(data["name"], "category")
    for key, value in data.items():
        setattr(row, key, value)
    db.add(row)
    commit(db)
    db.refresh(row)
    return row


def delete_category(db, identifier):
    row = category(db, identifier)
    if db.scalar(select(Article.id).where(Article.category_id == row.id).limit(1)):
        raise HTTPException(
            409, "انقل المقالات إلى تصنيف آخر أو أزل تصنيفها قبل حذف التصنيف"
        )
    db.delete(row)
    commit(db)


def list_categories(db, filters):
    statement = select(Category)
    if filters.q:
        statement = statement.where(
            Category.name.icontains(filters.q.strip(), autoescape=True)
        )
    order = (
        Category.name.asc()
        if filters.sort == "title"
        else (
            Category.created_at.asc()
            if filters.sort == "oldest"
            else Category.created_at.desc()
        )
    )
    return paginate(
        db, statement.order_by(order, Category.id), filters, CategoryOut.model_validate
    )


def article_scope(user, *, published_only=False):
    project_access = Article.project_id.in_(
        select(Project.id).where(visible_projects(user))
    )
    if published_only or user.role == Role.EMPLOYEE:
        return and_(
            Article.status == "published",
            or_(Article.project_id.is_(None), project_access),
        )
    if user.role == Role.ADMIN:
        return True
    return or_(
        and_(Article.project_id.is_(None), Article.status == "published"),
        project_access,
    )


def article_query():
    return select(Article).options(
        joinedload(Article.author),
        joinedload(Article.category),
        joinedload(Article.project),
    )


def can_edit(user, row):
    return not (row.project and row.project.is_archived) and (
        user.role == Role.ADMIN
        or (
            user.role == Role.MANAGER
            and row.project
            and row.project.manager_id == user.id
        )
    )


def article_out(row, user):
    values = {
        key: getattr(row, key)
        for key in ArticleOut.model_fields
        if key not in {"project_name", "can_edit"}
    }
    return ArticleOut(
        **values,
        project_name=row.project.name if row.project else None,
        can_edit=bool(can_edit(user, row))
    )


def get_article(db, identifier, user, *, edit=False):
    statement = article_query().where(
        Article.id == str(identifier), article_scope(user)
    )
    row = db.scalar(statement.execution_options(populate_existing=True))
    if row is None:
        raise HTTPException(404, "المقال غير موجود أو غير متاح")
    if edit:
        if row.project_id:
            get_project(db, row.project_id, user, write=True)
        else:
            if user.role != Role.ADMIN:
                raise HTTPException(403, "تعديل المقال العام متاح للمسؤول فقط")
        row = db.scalar(
            select(Article)
            .where(Article.id == row.id)
            .with_for_update()
            .execution_options(populate_existing=True)
        )
        if not can_edit(user, row):
            raise HTTPException(403, "لا تملك صلاحية تعديل هذا المقال")
    return row


def apply_dates(statement, model, filters):
    if (
        filters.updated_from
        and filters.updated_to
        and filters.updated_from > filters.updated_to
    ):
        raise HTTPException(422, "نطاق تاريخ التحديث غير صحيح")
    if filters.updated_from:
        statement = statement.where(
            model.updated_at
            >= datetime.combine(filters.updated_from, time.min, COMPANY_TZ)
        )
    if filters.updated_to:
        if filters.updated_to.year == 9999:
            raise HTTPException(422, "تاريخ التحديث خارج النطاق")
        statement = statement.where(
            model.updated_at
            < datetime.combine(
                filters.updated_to + timedelta(days=1), time.min, COMPANY_TZ
            )
        )
    return statement


def list_articles(db, user, filters):
    statement = article_query().where(article_scope(user))
    if filters.status != "all":
        statement = statement.where(Article.status == filters.status)
    if filters.q:
        statement = statement.where(
            Article.title.icontains(filters.q.strip(), autoescape=True)
        )
    if filters.category_id:
        statement = statement.where(Article.category_id == str(filters.category_id))
    if filters.project_id:
        statement = statement.where(Article.project_id == str(filters.project_id))
    if filters.language:
        statement = statement.where(Article.language == filters.language)
    statement = apply_dates(statement, Article, filters)
    order = (
        Article.title.asc()
        if filters.sort == "title"
        else (
            Article.updated_at.asc()
            if filters.sort == "oldest"
            else Article.updated_at.desc()
        )
    )
    return paginate(
        db,
        statement.order_by(order, Article.id),
        filters,
        lambda row: article_out(row, user),
    )


def record(db, user, row, action):
    db.add(ActivityLog(actor_id=user.id, article_id=row.id, action=action))


def save_article(db, user, payload, identifier=None):
    if user.role == Role.EMPLOYEE:
        raise HTTPException(403, "إنشاء المقالات وتعديلها متاح للمسؤول والمدير فقط")
    data = payload.model_dump(exclude_unset=True)
    if identifier:
        row = get_article(db, identifier, user, edit=True)
        if row.status == "archived":
            raise HTTPException(409, "المقال مؤرشف ولا يمكن تعديله")
    else:
        project_id = str(data["project_id"]) if data.get("project_id") else None
        if project_id:
            get_project(db, project_id, user, write=True)
        elif user.role != Role.ADMIN:
            raise HTTPException(403, "إنشاء المقال العام متاح للمسؤول فقط")
        data["project_id"] = project_id
        row = Article(id=str(uuid4()), author_id=user.id, status="draft")
    if data.get("category_id") is not None:
        data["category_id"] = category(db, data["category_id"]).id
    if data.get("slug") is not None:
        data["slug"] = valid_slug(data["slug"])
    elif not identifier:
        data["slug"] = slugify(data["title"], "article")
    if row.status == "published" and "content" in data and not data["content"].strip():
        raise HTTPException(400, "لا يمكن إفراغ محتوى مقال منشور")
    for key, value in data.items():
        setattr(row, key, value)
    db.add(row)
    try:
        db.flush()
    except IntegrityError:
        db.rollback()
        raise HTTPException(
            409, "المعرف النصي مستخدم أو البيانات مرتبطة بسجل غير متاح"
        ) from None
    record(db, user, row, "updated" if identifier else "created")
    commit(db)
    return article_out(get_article(db, row.id, user), user)


def transition(db, user, identifier, action):
    row = get_article(db, identifier, user, edit=True)
    if user.role == Role.EMPLOYEE:
        raise HTTPException(403, "لا تملك صلاحية نشر المقالات")
    if action == "publish":
        if row.status == "archived":
            raise HTTPException(409, "لا يمكن نشر مقال مؤرشف")
        if not row.content.strip() or not re.search(r"[\w\u0600-\u06ff]", row.content):
            raise HTTPException(400, "أضف محتوى صالحًا قبل النشر")
        if row.status != "published":
            row.published_at = utcnow()
        row.status = "published"
        row.archived_at = None
    else:
        row.status = "archived"
        row.archived_at = row.archived_at or utcnow()
    db.flush()
    record(db, user, row, action)
    commit(db)
    return article_out(get_article(db, row.id, user), user)
