import { useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import { ProjectForm } from "../components/ProjectForm";
import { Empty, ErrorBox, Loading, Pager } from "../components/WorkUI";
import { formatDate, projectStatuses, queryString } from "../work";
import type { Page, Person, Project } from "../work";

export function Projects({ user }: { user: User }) {
  const navigate = useNavigate();
  const managers = useResource<Person[]>("/project-managers");
  const [creating, setCreating] = useState(false);
  const [filters, setFilters] = useState({
    q: "",
    status: "",
    manager_id: "",
    created_from: "",
    created_to: "",
    archived: "false",
    sort_by: "created_at",
    sort_order: "desc",
    page: 1,
    page_size: 20,
  });
  const resource = useResource<Page<Project>>(
    `/projects?${queryString(filters)}`,
  );
  const update = (key: string, value: string | number) =>
    setFilters((previous) => ({ ...previous, [key]: value, page: 1 }));
  const [search, setSearch] = useState("");
  return (
    <>
      <div className="section-heading">
        <div>
          <span className="eyebrow">نظّم العمل وتابع التقدم</span>
          <h1>المشاريع</h1>
          <p className="muted">
            {user.role === "Admin"
              ? "جميع مشاريع الشركة في مكان واحد."
              : user.role === "Manager"
                ? "المشاريع التي تتولى إدارتها."
                : "المشاريع التي تنتمي إليها."}
          </p>
        </div>
        {user.role === "Admin" && !creating && (
          <button className="primary" onClick={() => setCreating(true)}>
            + مشروع جديد
          </button>
        )}
      </div>
      {creating && (
        <ProjectForm
          admin
          onCancel={() => setCreating(false)}
          onSaved={(project) => navigate(`/projects/${project.id}`)}
        />
      )}
      <section className="card filters">
        <form
          onSubmit={(event) => {
            event.preventDefault();
            update("q", search);
          }}
          className="search-row"
        >
          <label className="sr-only" htmlFor="project-search">
            البحث عن مشروع
          </label>
          <input
            id="project-search"
            placeholder="ابحث باسم المشروع…"
            value={search}
            maxLength={150}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button>بحث</button>
        </form>
        <div className="filter-grid">
          <label>
            الحالة
            <select
              aria-label="الحالة"
              value={filters.status}
              onChange={(event) => update("status", event.target.value)}
            >
              <option value="">كل الحالات</option>
              {Object.entries(projectStatuses).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            عرض المشاريع
            <select
              aria-label="عرض المشاريع"
              value={filters.archived}
              onChange={(event) => update("archived", event.target.value)}
            >
              <option value="false">غير المؤرشفة</option>
              <option value="true">المؤرشفة</option>
            </select>
          </label>
          <label>
            الترتيب
            <select
              aria-label="ترتيب المشاريع"
              value={filters.sort_by}
              onChange={(event) => update("sort_by", event.target.value)}
            >
              <option value="created_at">تاريخ الإنشاء</option>
              <option value="name">الاسم</option>
              <option value="start_date">تاريخ البداية</option>
              <option value="end_date">تاريخ النهاية</option>
            </select>
          </label>
          <label>
            الاتجاه
            <select
              aria-label="اتجاه ترتيب المشاريع"
              value={filters.sort_order}
              onChange={(event) => update("sort_order", event.target.value)}
            >
              <option value="desc">تنازلي</option>
              <option value="asc">تصاعدي</option>
            </select>
          </label>
        </div>
        <details>
          <summary>فلاتر إضافية</summary>
          <div className="filter-grid">
            <label>
              أنشئ من
              <input
                type="date"
                value={filters.created_from}
                onChange={(event) => update("created_from", event.target.value)}
              />
            </label>
            <label>
              أنشئ حتى
              <input
                type="date"
                value={filters.created_to}
                onChange={(event) => update("created_to", event.target.value)}
              />
            </label>
            <label>
              المدير المسؤول
              <select
                aria-label="المدير المسؤول"
                value={filters.manager_id}
                onChange={(event) => update("manager_id", event.target.value)}
              >
                <option value="">كل المديرين</option>
                {managers.data?.map((person) => (
                  <option value={person.id} key={person.id}>
                    {person.name}
                  </option>
                ))}
              </select>
            </label>
          </div>
          <ErrorBox error={managers.error} retry={managers.reload} />
        </details>
      </section>
      <ErrorBox error={resource.error} retry={resource.reload} />
      {resource.loading && <Loading />}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="project-grid">
              {resource.data.items.map((project) => (
                <article className="card project-card" key={project.id}>
                  <div className="card-meta">
                    <span className="pill">
                      {projectStatuses[project.status]}
                    </span>
                    {project.is_archived && (
                      <span className="archived-badge">مؤرشف</span>
                    )}
                  </div>
                  <h2>
                    <Link to={`/projects/${project.id}`}>{project.name}</Link>
                  </h2>
                  <p className="muted project-preview">
                    {project.description || "لم يُضف وصف لهذا المشروع."}
                  </p>
                  <dl>
                    <div>
                      <dt>مدير المشروع</dt>
                      <dd>{project.manager.name}</dd>
                    </div>
                    <div>
                      <dt>النهاية المتوقعة</dt>
                      <dd>{formatDate(project.end_date)}</dd>
                    </div>
                  </dl>
                  <Link className="project-link" to={`/projects/${project.id}`}>
                    فتح المشروع ←
                  </Link>
                </article>
              ))}
            </div>
          ) : (
            <Empty>
              جرّب تعديل البحث أو الفلاتر، أو أنشئ أول مشروع إذا كنت مسؤولًا.
            </Empty>
          )}
          <Pager
            result={resource.data}
            onPage={(page) => setFilters((previous) => ({ ...previous, page }))}
            onSize={(size) => update("page_size", size)}
          />
        </>
      )}
    </>
  );
}
