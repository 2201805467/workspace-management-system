import { useState } from "react";
import { Link } from "react-router-dom";
import { useResource } from "../hooks/useResource";
import type { SearchHit } from "../knowledge";
import type { Page } from "../work";
import { formatDate, queryString } from "../work";
import { Empty, ErrorBox, Loading, Pager } from "../components/WorkUI";
import { Highlight } from "../components/Markdown";
import { PagedChoice } from "../components/PagedChoice";

export function GlobalSearch() {
  const [query, setQuery] = useState("");
  const [filters, setFilters] = useState({
    q: "",
    type: "all",
    category_id: "",
    project_id: "",
    language: "",
    sort: "relevance",
    updated_from: "",
    updated_to: "",
    page: 1,
    page_size: 20,
  });
  const resource = useResource<Page<SearchHit>>(
    filters.q ? `/search?${queryString(filters)}` : null,
  );
  const update = (key: string, value: string | number) =>
    setFilters((old) => ({ ...old, [key]: value, page: 1 }));
  return (
    <>
      <span className="eyebrow">معلومة أقرب، وقت أقل</span>
      <h1>البحث الموحد</h1>
      <p className="muted">
        ابحث داخل المقالات المنشورة وأسماء الوثائق ونصوص PDF وWord المفهرسة.
      </p>
      <section className="card filters search-primary">
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            update("q", query.trim());
          }}
        >
          <label className="sr-only" htmlFor="global-query">
            كلمات البحث
          </label>
          <input
            id="global-query"
            required
            maxLength={200}
            value={query}
            placeholder="عن ماذا تبحث؟"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button className="primary" disabled={!query.trim()}>
            ابحث في المعرفة والوثائق
          </button>
        </form>
        <div className="filter-grid">
          <label>
            نوع النتائج
            <select
              aria-label="نوع النتائج"
              value={filters.type}
              onChange={(event) => update("type", event.target.value)}
            >
              <option value="all">المقالات والملفات</option>
              <option value="article">المقالات</option>
              <option value="file">الملفات</option>
            </select>
          </label>
          <PagedChoice
            path="/knowledge/categories"
            label="تصنيف النتائج"
            value={filters.category_id}
            onChange={(value) => update("category_id", value)}
          />
          <PagedChoice
            path="/projects"
            label="مشروع النتائج"
            value={filters.project_id}
            onChange={(value) => update("project_id", value)}
          />
          <label>
            لغة المقالات
            <select
              aria-label="لغة المقالات"
              value={filters.language}
              onChange={(event) => update("language", event.target.value)}
            >
              <option value="">كل اللغات</option>
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </label>
          <label>
            ترتيب النتائج
            <select
              aria-label="ترتيب النتائج"
              value={filters.sort}
              onChange={(event) => update("sort", event.target.value)}
            >
              <option value="relevance">الأكثر صلة</option>
              <option value="newest">الأحدث</option>
              <option value="oldest">الأقدم</option>
              <option value="title">العنوان</option>
            </select>
          </label>
          <label>
            تحديث النتائج من
            <input
              type="date"
              value={filters.updated_from}
              onChange={(event) => update("updated_from", event.target.value)}
            />
          </label>
          <label>
            تحديث النتائج حتى
            <input
              type="date"
              value={filters.updated_to}
              onChange={(event) => update("updated_to", event.target.value)}
            />
          </label>
        </div>
        {(filters.category_id || filters.language) && (
          <small className="muted">
            تصفية اللغة أو التصنيف تخص المقالات فقط وتستبعد الملفات.
          </small>
        )}
      </section>
      <ErrorBox error={resource.error} retry={resource.reload} />
      {resource.loading && <Loading />}
      {!filters.q && (
        <section className="empty-state">
          <h2>ابدأ بكلمة أو عبارة</h2>
          <p className="muted">تظهر لك النتائج المسموح بها فقط.</p>
        </section>
      )}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="search-results">
              {resource.data.items.map((item) => (
                <article
                  key={item.type + item.id}
                  className="card search-result"
                >
                  <div className="card-meta">
                    <span className="pill">
                      {item.type === "article" ? "مقال" : "ملف"}
                      {item.match_kind === "fuzzy" ? " · نتيجة قريبة" : ""}
                    </span>
                    <small className="muted">
                      {formatDate(item.updated_at)}
                    </small>
                  </div>
                  <h2>
                    <Link
                      to={
                        item.type === "article"
                          ? `/knowledge/${item.id}`
                          : `/projects/${item.project_id}`
                      }
                    >
                      <Highlight text={item.title} />
                    </Link>
                  </h2>
                  <p className="search-snippet">
                    <Highlight text={item.snippet} />
                  </p>
                  <small className="muted">
                    {item.project_name || "عام للشركة"}
                    {item.category_name ? ` · ${item.category_name}` : ""}
                  </small>
                  {item.type === "file" && (
                    <Link
                      className="project-link"
                      to={`/projects/${item.project_id}`}
                    >
                      فتح وثائق المشروع ←
                    </Link>
                  )}
                </article>
              ))}
            </div>
          ) : (
            <Empty>
              لا توجد نتائج مطابقة ضمن المحتوى المتاح لك. جرّب عبارة أخرى.
            </Empty>
          )}
          <Pager
            result={resource.data}
            onPage={(page) => setFilters((old) => ({ ...old, page }))}
            onSize={(size) => update("page_size", size)}
          />
        </>
      )}
    </>
  );
}
