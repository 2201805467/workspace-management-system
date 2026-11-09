import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { Member, Task } from "../work";
import { priorities, taskStatuses } from "../work";
import { ErrorBox } from "./WorkUI";

export function TaskForm({
  projectId,
  members,
  task,
  onSaved,
  onCancel,
}: {
  projectId: string;
  members: Member[];
  task?: Task;
  onSaved: (task: Task) => void;
  onCancel: () => void;
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    const data: Record<string, unknown> = {
      ...values,
      description: values.description || null,
      due_date: values.due_date || null,
    };
    if (task && data.assigned_to === task.assigned_to) delete data.assigned_to;
    setBusy(true);
    setError("");
    try {
      onSaved(
        await api<Task>(
          task ? `/tasks/${task.id}` : `/projects/${projectId}/tasks`,
          task ? "PATCH" : "POST",
          data,
        ),
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card editor">
      <div className="section-heading">
        <h2>{task ? "تعديل المهمة" : "مهمة جديدة"}</h2>
        <button type="button" onClick={onCancel} disabled={busy}>
          إلغاء
        </button>
      </div>
      <form onSubmit={submit}>
        <div className="form-grid">
          <div className="span-all">
            <label htmlFor="task-title">عنوان المهمة</label>
            <input
              id="task-title"
              name="title"
              required
              minLength={3}
              maxLength={200}
              defaultValue={task?.title}
            />
          </div>
          <div>
            <label htmlFor="assignee">الموظف المسؤول</label>
            <select
              id="assignee"
              name="assigned_to"
              defaultValue={task?.assigned_to || ""}
              required
            >
              <option value="" disabled>
                اختر عضوًا من المشروع
              </option>
              {members
                .filter(
                  (member) =>
                    member.user.is_active ||
                    member.user_id === task?.assigned_to,
                )
                .map((member) => (
                  <option key={member.id} value={member.user_id}>
                    {member.user.name}
                    {member.user.is_active ? "" : " (معطّل)"}
                  </option>
                ))}
            </select>
          </div>
          <div>
            <label htmlFor="task-status">حالة المهمة</label>
            <select
              id="task-status"
              name="status"
              defaultValue={task?.status || "todo"}
            >
              {Object.entries(taskStatuses).map(([key, label]) => (
                <option value={key} key={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="task-priority">الأولوية</label>
            <select
              id="task-priority"
              name="priority"
              defaultValue={task?.priority || "medium"}
            >
              {Object.entries(priorities).map(([key, label]) => (
                <option value={key} key={key}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="task-due">الموعد النهائي</label>
            <input
              id="task-due"
              name="due_date"
              type="date"
              defaultValue={task?.due_date || ""}
            />
          </div>
          <div className="span-all">
            <label htmlFor="task-description">وصف المهمة</label>
            <textarea
              id="task-description"
              name="description"
              maxLength={10000}
              rows={4}
              defaultValue={task?.description || ""}
            />
          </div>
        </div>
        <ErrorBox error={error} />
        <button className="primary" disabled={busy}>
          {busy ? "جارٍ الحفظ…" : task ? "حفظ المهمة" : "إنشاء المهمة"}
        </button>
      </form>
    </section>
  );
}
