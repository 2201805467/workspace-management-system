import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import { canEdit, formatDate, priorities, taskStatuses } from "../work";
import type { Member, Project, Task, TaskStatus } from "../work";
import { ErrorBox, Loading } from "../components/WorkUI";
import { TaskForm } from "../components/TaskForm";

export function TaskDetails({ user }: { user: User }) {
  const { taskId } = useParams();
  const task = useResource<Task>(`/tasks/${taskId}`);
  const project = useResource<Project>(
    task.data ? `/projects/${task.data.project_id}` : null,
  );
  const editor = project.data ? canEdit(user, project.data) : false;
  const members = useResource<Member[]>(
    editor && task.data ? `/projects/${task.data.project_id}/members` : null,
  );
  const [editing, setEditing] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function changeStatus(status: TaskStatus) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/tasks/${taskId}/status`, "PATCH", { status });
      task.reload();
      setNotice("تم تحديث الحالة.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  if (task.loading) return <Loading />;
  if (task.error) return <ErrorBox error={task.error} retry={task.reload} />;
  if (!task.data) return null;
  const item = task.data;
  const statusAllowed =
    !item.project_archived && (editor || item.assigned_to === user.id);
  return (
    <>
      <Link className="back-link" to={`/projects/${item.project_id}`}>
        ← {item.project_name}
      </Link>
      <div className="section-heading">
        <div>
          <span className="eyebrow">تفاصيل المهمة</span>
          <h1>{item.title}</h1>
          <span className={`priority priority-${item.priority}`}>
            {priorities[item.priority]}
          </span>
          {item.is_overdue && <span className="overdue-label"> · متأخرة</span>}
          {item.project_archived && (
            <span className="archived-badge">المشروع مؤرشف</span>
          )}
        </div>
        {editor && (
          <button onClick={() => setEditing(!editing)}>تعديل المهمة</button>
        )}
      </div>
      <ErrorBox error={project.error} retry={project.reload} />
      <ErrorBox error={members.error} retry={members.reload} />
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {editing &&
        editor &&
        (members.loading ? (
          <Loading />
        ) : (
          members.data && (
            <TaskForm
              task={item}
              projectId={item.project_id}
              members={members.data}
              onCancel={() => setEditing(false)}
              onSaved={() => {
                setEditing(false);
                task.reload();
                setNotice("تم حفظ المهمة.");
              }}
            />
          )
        ))}
      <section className="card">
        <h2>الوصف</h2>
        <p className="description">
          {item.description || "لم يُضف وصف لهذه المهمة."}
        </p>
        <dl className="detail-grid">
          <div>
            <dt>الموظف المسؤول</dt>
            <dd>{item.assignee.name}</dd>
          </div>
          <div>
            <dt>أنشأها</dt>
            <dd>{item.creator.name}</dd>
          </div>
          <div>
            <dt>الموعد النهائي</dt>
            <dd>{formatDate(item.due_date)}</dd>
          </div>
          <div>
            <dt>تاريخ الإنشاء</dt>
            <dd>{formatDate(item.created_at)}</dd>
          </div>
          <div>
            <dt>آخر تحديث</dt>
            <dd>{formatDate(item.updated_at)}</dd>
          </div>
          <div>
            <dt>تاريخ الإكمال</dt>
            <dd>{formatDate(item.completed_at)}</dd>
          </div>
        </dl>
        <label htmlFor="detail-status">حالة المهمة</label>
        {statusAllowed ? (
          <select
            className="status-editor"
            id="detail-status"
            value={item.status}
            disabled={busy}
            onChange={(event) =>
              void changeStatus(event.target.value as TaskStatus)
            }
          >
            {Object.entries(taskStatuses).map(([value, label]) => (
              <option key={value} value={value}>
                {label}
              </option>
            ))}
          </select>
        ) : (
          <p className={`task-status status-${item.status}`}>
            {taskStatuses[item.status]}
          </p>
        )}
      </section>
    </>
  );
}
