import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage, roleLabels } from "../api";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import { canEdit, formatDate, projectStatuses } from "../work";
import type { Member, Person, Project } from "../work";
import { ErrorBox, Loading } from "../components/WorkUI";
import { ProjectForm } from "../components/ProjectForm";
import { TaskList } from "../components/TaskList";
import { ProjectFiles } from "../components/ProjectFiles";

export function ProjectDetails({ user }: { user: User }) {
  const { projectId } = useParams();
  const project = useResource<Project>(`/projects/${projectId}`);
  const members = useResource<Member[]>(
    project.data ? `/projects/${projectId}/members` : null,
  );
  const editor = project.data ? canEdit(user, project.data) : false;
  const people = useResource<Person[]>(editor ? "/people" : null);
  const [editing, setEditing] = useState(false);
  const [memberId, setMemberId] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  async function changeMember(id?: string) {
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(
        `/projects/${projectId}/members${id ? `/${id}` : ""}`,
        id ? "DELETE" : "POST",
        id ? undefined : { user_id: memberId },
      );
      setMemberId("");
      members.reload();
      setNotice(id ? "تمت إزالة العضو." : "تمت إضافة العضو.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function archive() {
    if (
      !window.confirm(
        "أرشفة هذا المشروع؟ ستبقى بياناته محفوظة ويصبح متاحًا للقراءة فقط.",
      )
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/projects/${projectId}`, "DELETE");
      setEditing(false);
      project.reload();
      setNotice("تمت أرشفة المشروع.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  if (project.loading) return <Loading />;
  if (project.error)
    return (
      <>
        <Link to="/projects">← المشاريع</Link>
        <ErrorBox error={project.error} retry={project.reload} />
      </>
    );
  if (!project.data) return null;
  const item = project.data;
  return (
    <>
      <Link className="back-link" to="/projects">
        ← جميع المشاريع
      </Link>
      <div className="section-heading">
        <div>
          <span className="eyebrow">تفاصيل المشروع</span>
          <h1>{item.name}</h1>
          <div className="row-actions">
            <span className="pill">{projectStatuses[item.status]}</span>
            {item.is_archived && (
              <span className="archived-badge">مؤرشف · للقراءة فقط</span>
            )}
          </div>
        </div>
        <div className="row-actions">
          {editor && (
            <button onClick={() => setEditing(!editing)}>تعديل المشروع</button>
          )}
          {user.role === "Admin" && !item.is_archived && (
            <button
              className="danger-text"
              disabled={busy}
              onClick={() => void archive()}
            >
              أرشفة المشروع
            </button>
          )}
        </div>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {editing && editor && (
        <ProjectForm
          project={item}
          admin={user.role === "Admin"}
          onCancel={() => setEditing(false)}
          onSaved={() => {
            setEditing(false);
            project.reload();
            members.reload();
            setNotice("تم تحديث المشروع.");
          }}
        />
      )}
      <div className="project-overview">
        <section className="card">
          <h2>عن المشروع</h2>
          <p className="description">
            {item.description || "لا يوجد وصف لهذا المشروع."}
          </p>
          <dl className="detail-grid">
            <div>
              <dt>مدير المشروع</dt>
              <dd>{item.manager.name}</dd>
            </div>
            <div>
              <dt>تاريخ البداية</dt>
              <dd>{formatDate(item.start_date)}</dd>
            </div>
            <div>
              <dt>النهاية المتوقعة</dt>
              <dd>{formatDate(item.end_date)}</dd>
            </div>
            <div>
              <dt>آخر تحديث</dt>
              <dd>{formatDate(item.updated_at)}</dd>
            </div>
          </dl>
        </section>
        <section className="card">
          <h2>
            أعضاء المشروع{" "}
            <span className="count">{members.data?.length || 0}</span>
          </h2>
          <ErrorBox error={members.error} retry={members.reload} />
          {members.loading && <Loading />}
          <ul className="member-list">
            {members.data?.map((member) => (
              <li key={member.id}>
                <div>
                  <strong>{member.user.name}</strong>
                  <small>
                    {member.user_id === item.manager_id
                      ? "مدير المشروع"
                      : roleLabels[member.user.role]}
                    {!member.user.is_active && " · معطّل"}
                  </small>
                </div>
                {editor && member.user_id !== item.manager_id && (
                  <button
                    disabled={busy}
                    onClick={() => void changeMember(member.user_id)}
                  >
                    إزالة
                  </button>
                )}
              </li>
            ))}
          </ul>
          {editor && (
            <form
              className="add-member"
              onSubmit={(event) => {
                event.preventDefault();
                void changeMember();
              }}
            >
              <label htmlFor="add-member">إضافة عضو</label>
              <select
                id="add-member"
                required
                value={memberId}
                onChange={(event) => setMemberId(event.target.value)}
              >
                <option value="" disabled>
                  اختر موظفًا
                </option>
                {people.data
                  ?.filter(
                    (person) =>
                      !members.data?.some(
                        (member) => member.user_id === person.id,
                      ),
                  )
                  .map((person) => (
                    <option key={person.id} value={person.id}>
                      {person.name}
                    </option>
                  ))}
              </select>
              <ErrorBox error={people.error} retry={people.reload} />
              <button
                className="primary"
                disabled={
                  busy ||
                  people.loading ||
                  members.loading ||
                  Boolean(people.error) ||
                  Boolean(members.error) ||
                  !memberId
                }
              >
                إضافة للمشروع
              </button>
            </form>
          )}
        </section>
      </div>
      <TaskList
        key={item.id + String(item.is_archived)}
        user={user}
        project={item}
        members={members.data || []}
      />
      <ProjectFiles
        key={"files-" + item.id + String(item.is_archived)}
        user={user}
        project={item}
      />
    </>
  );
}
