import { useState } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import { formatDate, priorities, queryString, taskStatuses } from "../work";
import type { Member, Page, Project, Task, TaskStatus } from "../work";
import { Empty, ErrorBox, Loading, Pager } from "./WorkUI";
import { TaskForm } from "./TaskForm";

export function TaskList({
  user,
  project,
  members = [],
  mine = false,
}: {
  user: User;
  project?: Project;
  members?: Member[];
  mine?: boolean;
}) {
  const [filters, setFilters] = useState({
    q: "",
    status: "",
    priority: "",
    assigned_to: "",
    project_id: "",
    due_from: "",
    due_to: "",
    overdue: "",
    archived: "false",
    sort_by: "created_at",
    sort_order: "desc",
    page: 1,
    page_size: 20,
  });
  const [search, setSearch] = useState("");
  const [projectPage, setProjectPage] = useState(1);
  const [selectedProjectName, setSelectedProjectName] = useState("");
  const [editing, setEditing] = useState<Task | "new" | null>(null);
  const [busyId, setBusyId] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const endpoint = project ? `/projects/${project.id}/tasks` : "/tasks/my";
  const resource = useResource<Page<Task>>(
    `${endpoint}?${queryString(filters)}`,
  );
  const projects = useResource<Page<Project>>(
    mine
      ? `/projects?page=${projectPage}&page_size=20&archived=${filters.archived}`
      : null,
  );
  const editor =
    project &&
    !project.is_archived &&
    (user.role === "Admin" ||
      (user.role === "Manager" && project.manager_id === user.id));
  const update = (key: string, value: string | number) =>
    setFilters((previous) => ({ ...previous, [key]: value, page: 1 }));
  async function changeStatus(task: Task, status: TaskStatus) {
    setBusyId(task.id);
    setError("");
    setNotice("");
    try {
      await api(`/tasks/${task.id}/status`, "PATCH", { status });
      resource.reload();
      setNotice("تم تحديث حالة المهمة.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId("");
    }
  }
  async function remove(task: Task) {
    if (!window.confirm(`حذف المهمة «${task.title}» نهائيًا؟`)) return;
    setBusyId(task.id);
    setError("");
    setNotice("");
    try {
      await api(`/tasks/${task.id}`, "DELETE");
      resource.reload();
      setNotice("تم حذف المهمة.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId("");
    }
  }
  return (
    <section className="tasks-section">
      <div className="section-heading">
        <div>
          <h2>{mine ? "المهام المسندة إليك" : "مهام المشروع"}</h2>
          <p className="muted">
            ابحث وصفِّ النتائج، وتابع الحالة والموعد النهائي.
          </p>
        </div>
        {editor && !editing && (
          <button className="primary" onClick={() => setEditing("new")}>
            + مهمة جديدة
          </button>
        )}
      </div>
      {editing && project && (
        <TaskForm
          projectId={project.id}
          members={members}
          task={editing === "new" ? undefined : editing}
          onCancel={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            resource.reload();
            setNotice("تم حفظ المهمة.");
            setError("");
          }}
        />
      )}
      <section className="card filters">
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            update("q", search);
          }}
        >
          <label className="sr-only" htmlFor="task-search">
            البحث عن مهمة
          </label>
          <input
            id="task-search"
            placeholder="ابحث بعنوان المهمة…"
            value={search}
            maxLength={200}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button>بحث</button>
        </form>
        <div className="filter-grid">
          <label>
            حالة المهام
            <select
              aria-label="حالة المهام"
              value={filters.status}
              onChange={(event) => update("status", event.target.value)}
            >
              <option value="">كل الحالات</option>
              {Object.entries(taskStatuses).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            الأولوية
            <select
              aria-label="تصفية الأولوية"
              value={filters.priority}
              onChange={(event) => update("priority", event.target.value)}
            >
              <option value="">كل الأولويات</option>
              {Object.entries(priorities).map(([key, label]) => (
                <option key={key} value={key}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            التأخر
            <select
              aria-label="التأخر"
              value={filters.overdue}
              onChange={(event) => update("overdue", event.target.value)}
            >
              <option value="">كل المهام</option>
              <option value="true">المتأخرة فقط</option>
              <option value="false">غير المتأخرة</option>
            </select>
          </label>
          {project && (
            <label>
              الموظف
              <select
                aria-label="تصفية الموظف"
                value={filters.assigned_to}
                onChange={(event) => update("assigned_to", event.target.value)}
              >
                <option value="">كل الأعضاء</option>
                {members.map((member) => (
                  <option key={member.id} value={member.user_id}>
                    {member.user.name}
                  </option>
                ))}
              </select>
            </label>
          )}
          {mine && (
            <>
              <label>
                المشاريع
                <select
                  aria-label="تصفية المشروع"
                  value={filters.project_id}
                  onChange={(event) => {
                    update("project_id", event.target.value);
                    setSelectedProjectName(
                      event.target.selectedOptions[0].textContent || "",
                    );
                  }}
                >
                  <option value="">كل مشاريعي</option>
                  {filters.project_id &&
                    !projects.data?.items.some(
                      (project) => project.id === filters.project_id,
                    ) && (
                      <option value={filters.project_id}>
                        {selectedProjectName}
                      </option>
                    )}
                  {projects.data?.items.map((project) => (
                    <option key={project.id} value={project.id}>
                      {project.name}
                    </option>
                  ))}
                </select>
              </label>
              {projects.data && projects.data.total_pages > 1 && (
                <div className="project-picker-pages">
                  <span>
                    قائمة المشاريع: {projects.data.page} /{" "}
                    {projects.data.total_pages}
                  </span>
                  <div className="row-actions">
                    <button
                      type="button"
                      disabled={projects.loading || projectPage <= 1}
                      onClick={() => setProjectPage((page) => page - 1)}
                    >
                      مشاريع سابقة
                    </button>
                    <button
                      type="button"
                      disabled={
                        projects.loading ||
                        projectPage >= projects.data.total_pages
                      }
                      onClick={() => setProjectPage((page) => page + 1)}
                    >
                      مشاريع أخرى
                    </button>
                  </div>
                </div>
              )}
              <label>
                أرشفة المشروع
                <select
                  aria-label="أرشفة المشروع"
                  value={filters.archived}
                  onChange={(event) => {
                    setProjectPage(1);
                    setSelectedProjectName("");
                    setFilters((previous) => ({
                      ...previous,
                      archived: event.target.value,
                      project_id: "",
                      page: 1,
                    }));
                  }}
                >
                  <option value="false">غير المؤرشفة</option>
                  <option value="true">المؤرشفة</option>
                </select>
              </label>
            </>
          )}
        </div>
        <details>
          <summary>المواعيد والترتيب</summary>
          <div className="filter-grid">
            <label>
              الموعد من
              <input
                type="date"
                value={filters.due_from}
                onChange={(event) => update("due_from", event.target.value)}
              />
            </label>
            <label>
              الموعد حتى
              <input
                type="date"
                value={filters.due_to}
                onChange={(event) => update("due_to", event.target.value)}
              />
            </label>
            <label>
              ترتيب المهام
              <select
                aria-label="ترتيب المهام"
                value={filters.sort_by}
                onChange={(event) => update("sort_by", event.target.value)}
              >
                <option value="created_at">تاريخ الإنشاء</option>
                <option value="due_date">الموعد النهائي</option>
                <option value="priority">الأولوية</option>
              </select>
            </label>
            <label>
              اتجاه الترتيب
              <select
                aria-label="اتجاه ترتيب المهام"
                value={filters.sort_order}
                onChange={(event) => update("sort_order", event.target.value)}
              >
                <option value="desc">تنازلي</option>
                <option value="asc">تصاعدي</option>
              </select>
            </label>
          </div>
        </details>
      </section>
      <ErrorBox error={error} />
      <ErrorBox error={resource.error} retry={resource.reload} />
      <ErrorBox error={projects.error} retry={projects.reload} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {resource.loading && <Loading />}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="card task-table table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>المهمة</th>
                    {mine && <th>المشروع</th>}
                    <th>الموظف</th>
                    <th>الحالة</th>
                    <th>الأولوية</th>
                    <th>الموعد النهائي</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {resource.data.items.map((task) => {
                    const statusAllowed =
                      !task.project_archived &&
                      (Boolean(editor) ||
                        user.role === "Admin" ||
                        (user.role === "Manager" && mine) ||
                        task.assigned_to === user.id);
                    return (
                      <tr
                        key={task.id}
                        className={task.is_overdue ? "overdue-row" : ""}
                      >
                        <td>
                          <Link to={`/tasks/${task.id}`}>{task.title}</Link>
                          {task.is_overdue && (
                            <small className="overdue-label">متأخرة</small>
                          )}
                        </td>
                        {mine && (
                          <td>
                            <Link to={`/projects/${task.project_id}`}>
                              {task.project_name}
                            </Link>
                          </td>
                        )}
                        <td>{task.assignee.name}</td>
                        <td>
                          {statusAllowed ? (
                            <select
                              aria-label={`حالة ${task.title}`}
                              value={task.status}
                              disabled={Boolean(busyId)}
                              onChange={(event) =>
                                void changeStatus(
                                  task,
                                  event.target.value as TaskStatus,
                                )
                              }
                            >
                              {Object.entries(taskStatuses).map(
                                ([key, label]) => (
                                  <option key={key} value={key}>
                                    {label}
                                  </option>
                                ),
                              )}
                            </select>
                          ) : (
                            <span
                              className={`task-status status-${task.status}`}
                            >
                              {taskStatuses[task.status]}
                            </span>
                          )}
                        </td>
                        <td>
                          <span
                            className={`priority priority-${task.priority}`}
                          >
                            {priorities[task.priority]}
                          </span>
                        </td>
                        <td>{formatDate(task.due_date)}</td>
                        <td>
                          <div className="row-actions">
                            <Link to={`/tasks/${task.id}`}>التفاصيل</Link>
                            {editor && (
                              <>
                                <button
                                  disabled={Boolean(busyId)}
                                  onClick={() => setEditing(task)}
                                >
                                  تعديل
                                </button>
                                <button
                                  className="danger-text"
                                  disabled={Boolean(busyId)}
                                  onClick={() => void remove(task)}
                                >
                                  حذف
                                </button>
                              </>
                            )}
                          </div>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>لا توجد مهام تطابق البحث والفلاتر الحالية.</Empty>
          )}
          <Pager
            result={resource.data}
            onPage={(page) => setFilters((previous) => ({ ...previous, page }))}
            onSize={(size) => update("page_size", size)}
          />
        </>
      )}
    </section>
  );
}
