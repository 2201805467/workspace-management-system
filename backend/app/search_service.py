import re
from math import ceil

from fastapi import HTTPException
from sqlalchemy import (
    String,
    case,
    cast,
    func,
    literal,
    literal_column,
    or_,
    select,
    text,
    union_all,
)

from .models import (
    FileSearchIndex as FI,
    KnowledgeArticle as Article,
    KnowledgeCategory as Category,
    Project,
    ProjectFile,
)
from .knowledge_services import article_scope
from .work_repository import visible_projects


def normalize(value):
    value = value.replace("مسئول", "مسؤول")
    value = (
        re.sub("[ًٌٍَُِّْٰـ]", "", value)
        .translate(str.maketrans("أإآٱىؤئ", "اااايوي"))
        .lower()
    )
    return re.sub(r"\bال([ء-ي]{3,})", r"\1", value)


def highlight(value, query):
    # ts_headline output is TEXT, not trusted HTML. Add matches for normalized
    # Arabic variants while preserving original spelling in the excerpt.
    value = value.replace("\ue000", "").replace("\ue001", "")
    value = re.sub(r"(?m)^\s{0,3}#{1,6}\s*|[*_`~]", "", value)
    value = re.sub(r"\s+", " ", value).strip()
    if len(value) > 600:
        value = value[:600].rsplit(" ", 1)[0] + "…"
    words = {normalize(word) for word in re.findall(r"[\w\u064b-\u065f\u0670]+", query)}
    return re.sub(
        r"[\w\u064b-\u065f\u0670]+",
        lambda match: (
            "\ue000" + match.group() + "\ue001"
            if normalize(match.group()) in words
            else match.group()
        ),
        value,
    )


def search(db, user, filters):
    if db.get_bind().dialect.name != "postgresql":
        raise HTTPException(
            503, "البحث النصي يحتاج إلى تشغيل PostgreSQL وترحيلات البحث"
        )
    db.execute(text("SET LOCAL statement_timeout = '5000ms'"))
    db.execute(text("SET LOCAL pg_trgm.word_similarity_threshold = '0.45'"))
    normalized = func.workspace_normalize(filters.q)
    query = func.websearch_to_tsquery(
        literal_column("'public.workspace_arabic'::regconfig"), normalized
    ).op("||")(
        func.websearch_to_tsquery(
            literal_column("'pg_catalog.english'::regconfig"), normalized
        )
    )
    fuzzy = (
        len(normalize(filters.q)) >= 4
        and len(filters.q) <= 80
        and bool(re.fullmatch(r"[\w\s]+", filters.q))
    )
    sources = []

    def candidate(
        identifier,
        kind,
        title,
        body,
        project_id,
        category_name,
        updated,
        vector,
        normalized_title,
        statement,
    ):
        match = vector.op("@@")(query)
        similar = normalized_title.op("%>")(normalized) if fuzzy else literal(False)
        relevance = func.coalesce(func.ts_rank_cd(vector, query, 32), 0) * 10 + case(
            (normalized_title == normalized, 2.0), else_=0.0
        )
        if fuzzy:
            relevance = (
                relevance + func.word_similarity(normalized, normalized_title) * 0.25
            )
        statement = statement.with_only_columns(
            identifier.label("id"),
            literal(kind).label("type"),
            title.label("title"),
            body.label("body"),
            project_id.label("project_id"),
            Project.name.label("project_name"),
            category_name.label("category_name"),
            updated.label("updated_at"),
            relevance.label("relevance_score"),
            case((match, "full_text"), else_="fuzzy").label("match_kind"),
        )
        statement = statement.where(or_(match, similar))
        if filters.project_id:
            statement = statement.where(project_id == str(filters.project_id))
        if filters.updated_from:
            from datetime import datetime, time
            from .work_services import COMPANY_TZ

            statement = statement.where(
                updated >= datetime.combine(filters.updated_from, time.min, COMPANY_TZ)
            )
        if filters.updated_to:
            from datetime import datetime, time, timedelta
            from .work_services import COMPANY_TZ

            if filters.updated_to.year == 9999:
                raise HTTPException(422, "تاريخ التحديث خارج النطاق")
            statement = statement.where(
                updated
                < datetime.combine(
                    filters.updated_to + timedelta(days=1), time.min, COMPANY_TZ
                )
            )
        return statement

    if (
        filters.updated_from
        and filters.updated_to
        and filters.updated_from > filters.updated_to
    ):
        raise HTTPException(422, "نطاق تاريخ التحديث غير صحيح")
    if filters.type in {"all", "article"}:
        statement = (
            select(Article)
            .outerjoin(Project, Project.id == Article.project_id)
            .outerjoin(Category, Category.id == Article.category_id)
            .where(article_scope(user, published_only=True))
        )
        if filters.category_id:
            statement = statement.where(Article.category_id == str(filters.category_id))
        if filters.language:
            statement = statement.where(Article.language == filters.language)
        sources.append(
            candidate(
                Article.id,
                "article",
                Article.title,
                Article.summary + literal("\n") + Article.content,
                Article.project_id,
                Category.name,
                Article.updated_at,
                Article.search_vector,
                Article.search_title,
                statement,
            )
        )
    if (
        filters.type in {"all", "file"}
        and not filters.category_id
        and not filters.language
    ):
        statement = (
            select(ProjectFile)
            .join(Project, Project.id == ProjectFile.project_id)
            .join(FI, FI.file_id == ProjectFile.id)
            .where(ProjectFile.deleted_at.is_(None), visible_projects(user))
        )
        sources.append(
            candidate(
                ProjectFile.id,
                "file",
                ProjectFile.original_name,
                case((FI.indexing_status == "ready", FI.extracted_text), else_=""),
                ProjectFile.project_id,
                cast(literal(None), String),
                func.coalesce(FI.indexed_at, ProjectFile.created_at),
                FI.search_vector,
                FI.search_title,
                statement,
            )
        )
    if not sources:
        return dict(
            items=[],
            page=filters.page,
            page_size=filters.page_size,
            total=0,
            total_pages=0,
        )
    matched = union_all(*sources).subquery("authorized_matches")
    total = db.scalar(select(func.count()).select_from(matched))
    ordering = (
        [matched.c.relevance_score.desc(), matched.c.updated_at.desc()]
        if filters.sort == "relevance"
        else (
            [matched.c.title.asc()]
            if filters.sort == "title"
            else [
                (
                    matched.c.updated_at.asc()
                    if filters.sort == "oldest"
                    else matched.c.updated_at.desc()
                )
            ]
        )
    )
    page = (
        select(matched)
        .order_by(*ordering, matched.c.type, matched.c.id)
        .limit(filters.page_size)
        .offset((filters.page - 1) * filters.page_size)
        .subquery("result_page")
    )
    # Apply expensive excerpts ONLY after authorization, ranking and LIMIT.
    snippet_query = query.op("||")(
        func.plainto_tsquery(
            literal_column("'pg_catalog.simple'::regconfig"), filters.q
        )
    )
    excerpt = func.ts_headline(
        literal_column("'pg_catalog.simple'::regconfig"),
        func.coalesce(page.c.body, ""),
        snippet_query,
        "StartSel=\ue000, StopSel=\ue001, MaxWords=32, MinWords=12, MaxFragments=1",
    )
    columns = [column for column in page.c if column.key != "body"]
    result = (
        db.execute(select(*columns, func.left(excerpt, 800).label("snippet")))
        .mappings()
        .all()
    )
    items = [
        dict(row, snippet=highlight(row["snippet"] or row["title"], filters.q))
        for row in result
    ]
    return dict(
        items=items,
        page=filters.page,
        page_size=filters.page_size,
        total=total,
        total_pages=ceil(total / filters.page_size),
    )
