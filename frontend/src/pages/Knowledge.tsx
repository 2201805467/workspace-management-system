import { useState } from "react";
import { Link } from "react-router-dom";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import type { Article, Category } from "../knowledge";
import { articleStatuses } from "../knowledge";
import { formatDate, queryString } from "../work";
import type { Page } from "../work";
import { Empty, ErrorBox, Loading, Pager } from "../components/WorkUI";
import { PagedChoice } from "../components/PagedChoice";

export function Knowledge({ user }: { user: User }) {
  const [filters, setFilters] = useState({
    q: "",
    category_id: "",
    project_id: "",
    language: "",
    status: "published",
    sort: "newest",
    updated_from: "",
    updated_to: "",
    page: 1,
    page_size: 20,
  });
  const [query, setQuery] = useState("");
  const resource = useResource<Page<Article>>(
    `/knowledge/articles?${queryString(filters)}`,
  );
  const categories = useResource<Page<Category>>(
    "/knowledge/categories?page_size=20",
  );
  const update = (key: string, value: string | number) =>
    setFilters((old) => ({ ...old, [key]: value, page: 1 }));
  return (
    <>
      <div className="section-heading">
        <div>
          <span className="eyebrow">معرفة مشتركة، عمل أوضح</span>
          <h1>قاعدة المعرفة</h1>
          <p className="muted">إرشادات الشركة ومقالات المشاريع المتاحة لك.</p>
        </div>
        <div className="row-actions">
          <Link className="button-link" to="/search">
            البحث في المقالات والوثائق
          </Link>
          {user.role === "Admin" && (
            <Link className="button-link" to="/knowledge/categories">
              إدارة التصنيفات
            </Link>
          )}
          {user.role !== "Employee" && (
            <Link className="button-link primary" to="/knowledge/new">
              + مقال جديد
            </Link>
          )}
        </div>
      </div>
      <div className="category-chips">
        {categories.data?.items.map((category) => (
          <button
            className={filters.category_id === category.id ? "selected" : ""}
            key={category.id}
            onClick={() =>
              update(
                "category_id",
                filters.category_id === category.id ? "" : category.id,
              )
            }
          >
            {category.name}
          </button>
        ))}
      </div>
      <ErrorBox error={categories.error} retry={categories.reload} />
      <section className="card filters">
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            update("q", query);
          }}
        >
          <label className="sr-only" htmlFor="article-search">
            البحث عن مقال
          </label>
          <input
            id="article-search"
            value={query}
            maxLength={200}
            placeholder="ابحث في عناوين المقالات…"
            onChange={(event) => setQuery(event.target.value)}
          />
          <button>بحث في المقالات</button>
        </form>
        <div className="filter-grid">
          <PagedChoice
            path="/knowledge/categories"
            label="تصنيف المقال"
            value={filters.category_id}
            onChange={(value) => update("category_id", value)}
          />
          <PagedChoice
            path="/projects"
            label="مشروع المقال"
            value={filters.project_id}
            onChange={(value) => update("project_id", value)}
          />
          <label>
            لغة المقال
            <select
              aria-label="لغة المقال"
              value={filters.language}
              onChange={(event) => update("language", event.target.value)}
            >
              <option value="">كل اللغات</option>
              <option value="ar">العربية</option>
              <option value="en">English</option>
            </select>
          </label>
          {user.role !== "Employee" && (
            <label>
              حالة النشر
              <select
                aria-label="حالة النشر"
                value={filters.status}
                onChange={(event) => update("status", event.target.value)}
              >
                <option value="all">كل الحالات المسموح بها</option>
                {Object.entries(articleStatuses).map(([key, label]) => (
                  <option value={key} key={key}>
                    {label}
                  </option>
                ))}
              </select>
            </label>
          )}
          <label>
            ترتيب المقالات
            <select
              aria-label="ترتيب المقالات"
              value={filters.sort}
              onChange={(event) => update("sort", event.target.value)}
            >
              <option value="newest">الأحدث تحديثًا</option>
              <option value="oldest">الأقدم تحديثًا</option>
              <option value="title">العنوان</option>
            </select>
          </label>
          <label>
            تحديث من
            <input
              type="date"
              value={filters.updated_from}
              onChange={(event) => update("updated_from", event.target.value)}
            />
          </label>
          <label>
            تحديث حتى
            <input
              type="date"
              value={filters.updated_to}
              onChange={(event) => update("updated_to", event.target.value)}
            />
          </label>
        </div>
      </section>
      <ErrorBox error={resource.error} retry={resource.reload} />
      {resource.loading && <Loading />}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="article-grid">
              {resource.data.items.map((article) => (
                <article key={article.id} className="card article-card">
                  <div className="card-meta">
                    <span className="pill">
                      {article.category?.name || "دون تصنيف"}
                    </span>
                    <span
                      className={`task-status status-${article.status === "published" ? "done" : "todo"}`}
                    >
                      {articleStatuses[article.status]}
                    </span>
                  </div>
                  <h2>
                    <Link to={`/knowledge/${article.id}`}>{article.title}</Link>
                  </h2>
                  <p className="muted article-summary">
                    {article.summary || "افتح المقال لقراءة المحتوى."}
                  </p>
                  <small className="muted">
                    {article.project_name || "عام للشركة"} ·{" "}
                    {article.author.name} · {formatDate(article.updated_at)}
                  </small>
                  <Link
                    className="project-link"
                    to={`/knowledge/${article.id}`}
                  >
                    قراءة المقال ←
                  </Link>
                </article>
              ))}
            </div>
          ) : (
            <Empty>لا توجد مقالات تطابق الفلاتر الحالية.</Empty>
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
