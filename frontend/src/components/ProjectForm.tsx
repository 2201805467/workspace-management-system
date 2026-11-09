import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import { useResource } from "../hooks/useResource";
import { ErrorBox, Loading } from "./WorkUI";
import type { Person, Project } from "../work";
import { projectStatuses } from "../work";

export function ProjectForm({
  project,
  admin,
  onSaved,
  onCancel,
}: {
  project?: Project;
  admin: boolean;
  onSaved: (project: Project) => void;
  onCancel: () => void;
}) {
  const people = useResource<Person[]>(admin ? "/people" : null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const values = Object.fromEntries(new FormData(event.currentTarget));
    if (
      values.start_date &&
      values.end_date &&
      String(values.end_date) < String(values.start_date)
    ) {
      setError("تاريخ النهاية يجب أن يساوي تاريخ البداية أو يليه");
      return;
    }
    const data: Record<string, unknown> = {
      ...values,
      description: values.description || null,
      start_date: values.start_date || null,
      end_date: values.end_date || null,
    };
    if (project && data.manager_id === project.manager_id)
      delete data.manager_id;
    setBusy(true);
    setError("");
    try {
      onSaved(
        await api<Project>(
          project ? `/projects/${project.id}` : "/projects",
          project ? "PATCH" : "POST",
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
        <h2>{project ? "تعديل المشروع" : "مشروع جديد"}</h2>
        <button type="button" disabled={busy} onClick={onCancel}>
          إلغاء
        </button>
      </div>
      <ErrorBox error={people.error} retry={people.reload} />
      {people.loading && <Loading />}
      <form onSubmit={submit}>
        <div className="form-grid">
          <div>
            <label htmlFor="project-name">اسم المشروع</label>
            <input
              id="project-name"
              name="name"
              defaultValue={project?.name}
              required
              minLength={3}
              maxLength={150}
            />
          </div>
          {admin && (
            <div>
              <label htmlFor="manager">مدير المشروع</label>
              <select
                id="manager"
                name="manager_id"
                defaultValue={project?.manager_id || ""}
                required
              >
                <option value="" disabled>
                  اختر المدير
                </option>
                {project &&
                  !people.data?.some(
                    (person) => person.id === project.manager_id,
                  ) && (
                    <option value={project.manager_id}>
                      {project.manager.name} (معطّل)
                    </option>
                  )}
                {people.data
                  ?.filter((person) => person.role !== "Employee")
                  .map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name}
                    </option>
                  ))}
              </select>
            </div>
          )}
          <div>
            <label htmlFor="project-status">حالة المشروع</label>
            <select
              id="project-status"
              name="status"
              defaultValue={project?.status || "Planning"}
            >
              {Object.entries(projectStatuses).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </div>
          <div>
            <label htmlFor="start-date">تاريخ البداية</label>
            <input
              id="start-date"
              name="start_date"
              type="date"
              defaultValue={project?.start_date || ""}
            />
          </div>
          <div>
            <label htmlFor="end-date">تاريخ النهاية المتوقع</label>
            <input
              id="end-date"
              name="end_date"
              type="date"
              defaultValue={project?.end_date || ""}
            />
          </div>
          <div className="span-all">
            <label htmlFor="project-description">وصف المشروع</label>
            <textarea
              id="project-description"
              name="description"
              maxLength={10000}
              rows={4}
              defaultValue={project?.description || ""}
            />
          </div>
        </div>
        <ErrorBox error={error} />
        <button
          className="primary"
          disabled={busy || people.loading || Boolean(people.error)}
        >
          {busy ? "جارٍ الحفظ…" : project ? "حفظ المشروع" : "إنشاء المشروع"}
        </button>
      </form>
    </section>
  );
}
