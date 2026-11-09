import { useEffect, useState } from "react";
import {
  Navigate,
  Route,
  Routes,
  useLocation,
  useNavigate,
} from "react-router-dom";
import { api, ApiError, errorMessage, roleLabels } from "./api";
import type { User } from "./api";
import { Brand } from "./components/Brand";
import { Login } from "./pages/Login";
import { PasswordForm } from "./pages/PasswordForm";
import { Users } from "./pages/Users";
import { Projects } from "./pages/Projects";
import { ProjectDetails } from "./pages/ProjectDetails";
import { TaskDetails } from "./pages/TaskDetails";
import { MyTasks } from "./pages/MyTasks";
import "./Work.css";
import "./App.css";

function App() {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [bootError, setBootError] = useState("");
  const [notice, setNotice] = useState("");
  const location = useLocation();
  const navigate = useNavigate();
  const page = location.pathname.startsWith("/projects")
    ? "projects"
    : location.pathname.startsWith("/tasks/")
      ? "task"
      : location.pathname === "/my-tasks"
        ? "my-tasks"
        : location.pathname === "/users"
          ? "users"
          : location.pathname === "/password"
            ? "password"
            : "home";
  const setPage = (page: string) =>
    navigate(page === "home" ? "/" : `/${page}`);
  const [logoutError, setLogoutError] = useState("");
  const [loggingOut, setLoggingOut] = useState(false);
  useEffect(() => {
    let active = true;
    api<User>("/auth/me", "GET", undefined, false)
      .then((user) => {
        if (active) setUser(user);
      })
      .catch((error) => {
        if (active && !(error instanceof ApiError && error.status === 401))
          setBootError(errorMessage(error));
      })
      .finally(() => {
        if (active) setLoading(false);
      });
    const expired = () => {
      setUser(null);
      setNotice("انتهت الجلسة. يرجى تسجيل الدخول مجددًا.");
    };
    window.addEventListener("session-expired", expired);
    return () => {
      active = false;
      window.removeEventListener("session-expired", expired);
    };
  }, []);
  async function logout() {
    setLogoutError("");
    setLoggingOut(true);
    try {
      await api("/auth/logout", "POST");
      setUser(null);
      setNotice("تم تسجيل الخروج بأمان.");
      setPage("home");
    } catch (error) {
      setLogoutError(errorMessage(error));
    } finally {
      setLoggingOut(false);
    }
  }
  if (loading)
    return (
      <div className="loading" role="status">
        <Brand />
        <p>جارٍ التحقق من الجلسة…</p>
      </div>
    );
  if (!user && location.pathname !== "/login")
    return <Navigate to="/login" replace />;
  if (!user)
    return (
      <Login
        notice={bootError || notice}
        onLogin={(user) => {
          setUser(user);
          setNotice("");
          setBootError("");
          setPage("home");
        }}
      />
    );
  if (
    location.pathname === "/login" ||
    (!["/", "/users", "/password", "/projects", "/my-tasks"].includes(
      location.pathname,
    ) &&
      !/^\/(projects|tasks)\/[^/]+$/.test(location.pathname))
  )
    return <Navigate to="/" replace />;
  if (page === "users" && user.role !== "Admin")
    return <Navigate to="/" replace />;
  return (
    <div className="app-layout">
      <aside className="sidebar">
        <Brand />
        <span className="nav-label">مساحة العمل</span>
        <nav aria-label="التنقل الرئيسي">
          <button
            className={page === "home" ? "selected" : ""}
            onClick={() => setPage("home")}
          >
            الرئيسية <span>⌂</span>
          </button>
          <button
            className={page === "projects" ? "selected" : ""}
            onClick={() => setPage("projects")}
          >
            المشاريع <span>▦</span>
          </button>
          <button
            className={page === "my-tasks" ? "selected" : ""}
            onClick={() => setPage("my-tasks")}
          >
            مهامي <span>✓</span>
          </button>
          {user.role === "Admin" && (
            <button
              className={page === "users" ? "selected" : ""}
              onClick={() => setPage("users")}
            >
              حسابات الفريق <span>♧</span>
            </button>
          )}
          <button
            className={page === "password" ? "selected" : ""}
            onClick={() => setPage("password")}
          >
            كلمة المرور <span>⚿</span>
          </button>
        </nav>
        <div className="sidebar-bottom">
          <span className="avatar">{user.name.slice(0, 1)}</span>
          <div>
            <strong>{user.name}</strong>
            <small>{roleLabels[user.role]}</small>
          </div>
        </div>
      </aside>
      <div className="workspace">
        <header>
          <span>
            الشركة /{" "}
            {page === "projects"
              ? "المشاريع"
              : page === "my-tasks"
                ? "مهامي"
                : page === "task"
                  ? "تفاصيل المهمة"
                  : page === "home"
                    ? "الرئيسية"
                    : page === "users"
                      ? "حسابات الفريق"
                      : "كلمة المرور"}
          </span>
          <button disabled={loggingOut} onClick={() => void logout()}>
            {loggingOut ? "جارٍ الخروج…" : "تسجيل الخروج ↗"}
          </button>
        </header>
        <main className="workspace-content">
          {logoutError && (
            <p className="error" role="alert">
              {logoutError}
            </p>
          )}
          {page === "home" && (
            <>
              <span className="eyebrow">أهلًا بك في مساحة العمل</span>
              <h1>
                مرحبًا، {user.name}
                <span className="accent">.</span>
              </h1>
              <p className="muted">تم تسجيل دخولك. حسابك جاهز لبدء العمل.</p>
              <section className="welcome-card">
                <span className="pill">مساحة عمل الشركة</span>
                <h2>
                  كل مشروع له وجهة.
                  <br />
                  وكل مهمة تقرّبك منها.
                </h2>
                <p>
                  يمكنك الآن إدارة حسابك
                  {user.role === "Admin"
                    ? " وإنشاء حسابات فريقك وتحديد أدوارهم"
                    : ""}
                  .
                </p>
                {user.role === "Admin" ? (
                  <button className="primary" onClick={() => setPage("users")}>
                    إدارة حسابات الفريق ←
                  </button>
                ) : (
                  <button
                    className="primary"
                    onClick={() => setPage("password")}
                  >
                    إعداد كلمة المرور ←
                  </button>
                )}
              </section>
              <div className="home-links">
                <button className="primary" onClick={() => setPage("projects")}>
                  تصفح المشاريع ←
                </button>
                <button onClick={() => setPage("my-tasks")}>عرض مهامي ←</button>
              </div>
              <section className="card profile-card">
                <h2>حسابك</h2>
                <dl>
                  <div>
                    <dt>البريد الإلكتروني</dt>
                    <dd dir="ltr">{user.email}</dd>
                  </div>
                  <div>
                    <dt>الدور</dt>
                    <dd>{roleLabels[user.role]}</dd>
                  </div>
                  <div>
                    <dt>حالة الحساب</dt>
                    <dd>
                      <span className="status">نشط</span>
                    </dd>
                  </div>
                </dl>
              </section>
            </>
          )}
          <Routes>
            <Route path="/projects" element={<Projects user={user} />} />
            <Route
              path="/projects/:projectId"
              element={<ProjectDetails key={location.pathname} user={user} />}
            />
            <Route
              path="/tasks/:taskId"
              element={<TaskDetails key={location.pathname} user={user} />}
            />
            <Route path="/my-tasks" element={<MyTasks user={user} />} />
            <Route path="/" element={null} />
            <Route path="/users" element={null} />
            <Route path="/password" element={null} />
          </Routes>
          {page === "users" && user.role === "Admin" && <Users self={user} />}
          {page === "password" && (
            <PasswordForm
              onChanged={() => {
                setUser(null);
                setPage("home");
                setNotice(
                  "تم تغيير كلمة المرور وإغلاق الجلسات. سجّل الدخول بكلمتك الجديدة.",
                );
              }}
            />
          )}
        </main>
        <footer>
          WorkSpace <span>مساحة عمل الشركة</span>
        </footer>
      </div>
    </div>
  );
}

export default App;
