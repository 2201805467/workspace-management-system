import { useState } from "react";
import type { FormEvent } from "react";
import { api, errorMessage } from "../api";
import type { User } from "../api";
import { Brand } from "../components/Brand";

export function Login({
  onLogin,
  notice,
}: {
  onLogin: (user: User) => void;
  notice: string;
}) {
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [visible, setVisible] = useState(false);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const data = new FormData(event.currentTarget);
    setError("");
    setBusy(true);
    try {
      onLogin(
        await api<User>("/auth/login", "POST", {
          email: data.get("email"),
          password: data.get("password"),
        }),
      );
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <main className="login-layout">
      <section className="login-panel">
        <Brand />
        <div className="login-content">
          <span className="eyebrow">مساحة عمل الشركة</span>
          <h1>
            مرحبًا بعودتك<span className="accent">.</span>
          </h1>
          <p className="muted">
            سجّل الدخول إلى حسابك للمتابعة إلى مساحة العمل.
          </p>
          {notice && (
            <p className="notice" role="status">
              {notice}
            </p>
          )}
          <form onSubmit={submit}>
            <label htmlFor="email">البريد الإلكتروني</label>
            <input
              id="email"
              name="email"
              type="email"
              dir="ltr"
              autoComplete="username"
              placeholder="name@company.com"
              required
              maxLength={254}
            />
            <label htmlFor="password">كلمة المرور</label>
            <div className="password-input">
              <input
                id="password"
                name="password"
                type={visible ? "text" : "password"}
                autoComplete="current-password"
                required
                maxLength={128}
              />
              <button
                type="button"
                className="text-button"
                onClick={() => setVisible(!visible)}
                aria-pressed={visible}
              >
                {visible ? "إخفاء" : "إظهار"}
              </button>
            </div>
            {error && (
              <p className="error" role="alert">
                {error}
              </p>
            )}
            <button className="primary full" disabled={busy}>
              {busy ? "جارٍ تسجيل الدخول…" : "تسجيل الدخول ←"}
            </button>
          </form>
          <p className="account-help">
            ليس لديك حساب أو نسيت كلمة المرور؟
            <br />
            <strong>تواصل مع مسؤول النظام في شركتك.</strong>
          </p>
        </div>
        <footer>
          WorkSpace <span>نظام إدارة أعمال الشركة</span>
        </footer>
      </section>
      <aside className="intro-panel">
        <span className="intro-label">
          <i /> مساحة عمل داخلية
        </span>
        <div className="intro-copy">
          <span className="eyebrow">كل شيء يبدأ من هنا</span>
          <h2>
            فريقك.
            <br />
            أعمالك.
            <br />
            <span>في مساحة واحدة.</span>
          </h2>
          <p>
            مكان يجمع فريقك وينظّم العمل،
            <br />
            لتبقى الصورة واضحة للجميع.
          </p>
        </div>
        <div className="intro-footer">
          <span>01 / الأساس</span>
          <span>تواصل. نظّم. أنجز.</span>
        </div>
        <div className="orbit orbit-one" />
        <div className="orbit orbit-two" />
      </aside>
    </main>
  );
}
