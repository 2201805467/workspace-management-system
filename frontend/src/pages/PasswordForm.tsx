import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";

export function PasswordForm({ onChanged }: { onChanged: () => void }) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    if (data.get("new_password") !== data.get("confirm")) {
      setError("كلمتا المرور الجديدتان غير متطابقتين");
      return;
    }
    setBusy(true);
    setError("");
    try {
      await api("/auth/change-password", "POST", {
        current_password: data.get("current_password"),
        new_password: data.get("new_password"),
      });
      onChanged();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="card narrow">
      <h2>تغيير كلمة المرور</h2>
      <p className="muted">
        بعد التغيير، ستُغلق جميع جلسات حسابك وستسجّل الدخول مجددًا.
      </p>
      <form onSubmit={submit}>
        <label htmlFor="current_password">كلمة المرور الحالية</label>
        <input
          id="current_password"
          name="current_password"
          type="password"
          autoComplete="current-password"
          required
          maxLength={128}
        />
        <label htmlFor="new_password">كلمة المرور الجديدة</label>
        <input
          id="new_password"
          name="new_password"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
        />
        <small className="muted">12 حرفًا على الأقل</small>
        <label htmlFor="confirm">تأكيد كلمة المرور</label>
        <input
          id="confirm"
          name="confirm"
          type="password"
          autoComplete="new-password"
          required
          minLength={12}
          maxLength={128}
        />
        {error && (
          <p className="error" role="alert">
            {error}
          </p>
        )}
        <button className="primary" disabled={busy}>
          {busy ? "جارٍ الحفظ…" : "حفظ كلمة المرور"}
        </button>
      </form>
    </section>
  );
}
