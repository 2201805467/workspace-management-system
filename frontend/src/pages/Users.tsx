import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import { roleLabels } from "../api";
import type { Role, User } from "../api";

export function Users({ self }: { self: User }) {
  const [users, setUsers] = useState<User[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [resetUser, setResetUser] = useState<User | null>(null);
  async function load() {
    setLoading(true);
    try {
      setUsers(await api<User[]>("/users"));
      setError("");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setLoading(false);
    }
  }
  useEffect(() => {
    void load();
  }, []);
  async function create(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const data = new FormData(form);
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const user = await api<User>("/users", "POST", Object.fromEntries(data));
      setUsers((users) => [...users, user]);
      form.reset();
      setMessage("تم إنشاء الحساب. سلّم بيانات الدخول للموظف بطريقة آمنة.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function toggle(user: User) {
    setBusy(true);
    setError("");
    setMessage("");
    try {
      const updated = await api<User>(`/users/${user.id}/status`, "PATCH", {
        is_active: !user.is_active,
      });
      setUsers((users) =>
        users.map((item) => (item.id === updated.id ? updated : item)),
      );
      setMessage(
        updated.is_active
          ? "تم تفعيل الحساب."
          : "تم تعطيل الحساب وإغلاق جلساته.",
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function resetPassword(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!resetUser) return;
    const data = new FormData(event.currentTarget);
    setBusy(true);
    setError("");
    setMessage("");
    try {
      await api(`/users/${resetUser.id}/reset-password`, "POST", {
        new_password: data.get("password"),
      });
      setResetUser(null);
      setMessage("تمت إعادة تعيين كلمة المرور وإغلاق جلسات الحساب.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <div className="section-heading">
        <div>
          <h1>حسابات الفريق</h1>
          <p className="muted">إنشاء الحسابات والتحكم في وصول أعضاء الشركة.</p>
        </div>
        <span className="pill">{users.length} حساب</span>
      </div>
      {error && (
        <div className="error" role="alert">
          {error}{" "}
          <button className="text-button" onClick={() => void load()}>
            إعادة تحميل القائمة
          </button>
        </div>
      )}
      {message && (
        <p className="notice" role="status">
          {message}
        </p>
      )}
      <div className="users-layout">
        <section className="card user-list">
          <h2>أعضاء الشركة</h2>
          {loading ? (
            <p role="status">جارٍ تحميل الحسابات…</p>
          ) : (
            <div className="table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>الموظف</th>
                    <th>الدور</th>
                    <th>الحالة</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {users.map((user) => (
                    <tr key={user.id}>
                      <td>
                        <strong>{user.name}</strong>
                        <small dir="ltr">{user.email}</small>
                      </td>
                      <td>{roleLabels[user.role]}</td>
                      <td>
                        <span
                          className={`status ${user.is_active ? "" : "inactive"}`}
                        >
                          {user.is_active ? "نشط" : "معطّل"}
                        </span>
                      </td>
                      <td>
                        {user.id === self.id ? (
                          <span className="muted">حسابك الحالي</span>
                        ) : (
                          <div className="row-actions">
                            <button
                              disabled={busy}
                              onClick={() => void toggle(user)}
                            >
                              {user.is_active ? "تعطيل" : "تفعيل"}
                            </button>
                            <button
                              disabled={busy}
                              onClick={() => {
                                setResetUser(user);
                                setError("");
                                setMessage("");
                              }}
                            >
                              إعادة تعيين كلمة المرور
                            </button>
                          </div>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}
        </section>
        <section className="card">
          <h2>حساب جديد</h2>
          <form onSubmit={create}>
            <label htmlFor="name">الاسم الكامل</label>
            <input
              id="name"
              name="name"
              required
              minLength={2}
              maxLength={100}
              autoComplete="name"
            />
            <label htmlFor="user-email">البريد الإلكتروني</label>
            <input
              id="user-email"
              name="email"
              dir="ltr"
              type="email"
              autoComplete="off"
              required
              maxLength={254}
            />
            <label htmlFor="role">الدور</label>
            <select id="role" name="role" defaultValue="Employee">
              {(Object.keys(roleLabels) as Role[]).map((role) => (
                <option key={role} value={role}>
                  {roleLabels[role]}
                </option>
              ))}
            </select>
            <label htmlFor="initial-password">كلمة المرور الأولية</label>
            <input
              id="initial-password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
            />
            <small className="muted">12 حرفًا على الأقل</small>
            <button className="primary full" disabled={busy}>
              {busy ? "جارٍ التنفيذ…" : "+ إنشاء الحساب"}
            </button>
          </form>
        </section>
      </div>
      {resetUser && (
        <section
          className="card narrow reset-card"
          aria-label="إعادة تعيين كلمة المرور"
        >
          <h2>كلمة مرور جديدة: {resetUser.name}</h2>
          <p className="muted">سيتم إغلاق جميع جلسات هذا الحساب.</p>
          <form onSubmit={resetPassword}>
            <label htmlFor="reset-password">كلمة المرور الجديدة</label>
            <input
              id="reset-password"
              name="password"
              type="password"
              autoComplete="new-password"
              required
              minLength={12}
              maxLength={128}
            />
            <div className="row-actions">
              <button className="primary" disabled={busy}>
                حفظ
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setResetUser(null)}
              >
                إلغاء
              </button>
            </div>
          </form>
        </section>
      )}
    </>
  );
}
