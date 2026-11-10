import { useEffect, useState } from "react";
import type { FormEvent } from "react";
import { Link, useBlocker, useNavigate, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import type { User } from "../api";
import type { Article } from "../knowledge";
import { useResource } from "../hooks/useResource";
import { ErrorBox, Loading } from "../components/WorkUI";
import { Markdown } from "../components/Markdown";
import { PagedChoice } from "../components/PagedChoice";

function Editor({ user, article }: { user: User; article?: Article }) {
  const navigate = useNavigate();
  const [values, setValues] = useState({
    title: article?.title || "",
    slug: article?.slug || "",
    summary: article?.summary || "",
    content: article?.content || "",
    category_id: article?.category_id || "",
    project_id: article?.project_id || "",
    language: article?.language || "ar",
  });
  const [scope, setScope] = useState(
    article?.project_id || user.role === "Manager" ? "project" : "company",
  );
  const [saved, setSaved] = useState<Article | undefined>(article);
  const [dirty, setDirty] = useState(false),
    [busy, setBusy] = useState(false),
    [preview, setPreview] = useState(false),
    [error, setError] = useState("");
  const blocker = useBlocker(dirty && !busy);
  useEffect(() => {
    if (blocker.state === "blocked") {
      if (window.confirm("لديك تعديلات غير محفوظة. هل تريد مغادرة الصفحة؟"))
        blocker.proceed();
      else blocker.reset();
    }
  }, [blocker]);
  useEffect(() => {
    const before = (event: BeforeUnloadEvent) => {
      if (dirty) {
        event.preventDefault();
        event.returnValue = "";
      }
    };
    window.addEventListener("beforeunload", before);
    return () => window.removeEventListener("beforeunload", before);
  }, [dirty]);
  const update = (key: string, value: string) => {
    setValues((old) => ({ ...old, [key]: value }));
    setDirty(true);
  };
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setBusy(true);
    setError("");
    const publish =
      (event.nativeEvent as SubmitEvent).submitter?.getAttribute("value") ===
      "publish";
    const body: Record<string, unknown> = {
      title: values.title,
      summary: values.summary,
      content: values.content,
      category_id: values.category_id || null,
      language: values.language,
    };
    if (values.slug) body.slug = values.slug;
    if (!saved)
      body.project_id = scope === "project" ? values.project_id : null;
    try {
      let result = await api<Article>(
        saved ? `/knowledge/articles/${saved.id}` : "/knowledge/articles",
        saved ? "PATCH" : "POST",
        body,
      );
      setSaved(result);
      setDirty(false);
      if (publish)
        result = await api<Article>(
          `/knowledge/articles/${result.id}/publish`,
          "POST",
        );
      navigate(`/knowledge/${result.id}`);
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link
        className="back-link"
        to={article ? `/knowledge/${article.id}` : "/knowledge"}
      >
        ← العودة
      </Link>
      <div className="section-heading">
        <h1>{article ? "تعديل المقال" : "مقال جديد"}</h1>
        {dirty && <span className="unsaved">تغييرات غير محفوظة</span>}
      </div>
      <ErrorBox error={error} />
      <form onSubmit={submit} className="card article-editor">
        <fieldset disabled={busy}>
          <div className="form-grid">
            <div className="span-all">
              <label htmlFor="article-title">عنوان المقال</label>
              <input
                id="article-title"
                required
                minLength={5}
                maxLength={200}
                value={values.title}
                onChange={(event) => update("title", event.target.value)}
              />
            </div>
            <div>
              <label htmlFor="article-slug">المعرف النصي للمقال</label>
              <input
                id="article-slug"
                minLength={3}
                maxLength={200}
                value={values.slug}
                placeholder="يُنشأ تلقائيًا"
                onChange={(event) => update("slug", event.target.value)}
              />
            </div>
            <PagedChoice
              path="/knowledge/categories"
              label="تصنيف المقال"
              value={values.category_id}
              initialLabel={article?.category?.name}
              empty="دون تصنيف"
              onChange={(value) => update("category_id", value)}
            />
            <div>
              <label htmlFor="article-language">لغة المقال</label>
              <select
                id="article-language"
                value={values.language}
                onChange={(event) => update("language", event.target.value)}
              >
                <option value="ar">العربية</option>
                <option value="en">English</option>
              </select>
            </div>
            <div>
              <label htmlFor="article-scope">نطاق المقال</label>
              <select
                id="article-scope"
                value={scope}
                disabled={Boolean(saved) || user.role === "Manager"}
                onChange={(event) => {
                  setScope(event.target.value);
                  setDirty(true);
                }}
              >
                {user.role === "Admin" && (
                  <option value="company">عام للشركة</option>
                )}
                <option value="project">خاص بمشروع</option>
              </select>
            </div>
            {scope === "project" && (
              <PagedChoice
                path="/projects"
                label="المشروع المرتبط"
                value={values.project_id}
                initialLabel={article?.project_name || ""}
                required
                disabled={Boolean(saved)}
                empty="اختر المشروع"
                onChange={(value) => update("project_id", value)}
              />
            )}
            <div className="span-all">
              <label htmlFor="article-summary">ملخص المقال</label>
              <textarea
                id="article-summary"
                rows={3}
                maxLength={1000}
                value={values.summary}
                onChange={(event) => update("summary", event.target.value)}
              />
            </div>
          </div>
          <div className="section-heading editor-toolbar">
            <label htmlFor="article-content">محتوى المقال بصيغة Markdown</label>
            <button type="button" onClick={() => setPreview(!preview)}>
              {preview ? "العودة للتحرير" : "معاينة Markdown"}
            </button>
          </div>
          {preview ? (
            <section className="markdown-preview" aria-label="معاينة المقال">
              <Markdown content={values.content} />
            </section>
          ) : (
            <textarea
              id="article-content"
              className="markdown-input"
              rows={18}
              maxLength={50000}
              value={values.content}
              onChange={(event) => update("content", event.target.value)}
              placeholder={"# عنوان رئيسي\n\nاكتب الإرشادات هنا…"}
            />
          )}
          <p className="muted">
            {values.content.length.toLocaleString()} / 50,000 · يدعم العناوين
            والقوائم والروابط والأكواد.
          </p>
          <div className="row-actions">
            <button className="primary" value="save" disabled={busy}>
              {busy
                ? "جارٍ الحفظ…"
                : saved?.status === "published"
                  ? "حفظ التعديلات"
                  : "حفظ المسودة"}
            </button>
            <button value="publish" disabled={busy || !values.content.trim()}>
              حفظ ونشر
            </button>
          </div>
        </fieldset>
      </form>
    </>
  );
}

export function ArticleEditor({ user }: { user: User }) {
  const { articleId } = useParams();
  const resource = useResource<Article>(
    articleId ? `/knowledge/articles/${articleId}` : null,
  );
  if (resource.loading) return <Loading />;
  if (resource.error)
    return <ErrorBox error={resource.error} retry={resource.reload} />;
  if (
    articleId &&
    (!resource.data ||
      !resource.data.can_edit ||
      resource.data.status === "archived")
  )
    return <ErrorBox error="هذا المقال غير متاح للتعديل" />;
  return (
    <Editor
      key={articleId || "new"}
      user={user}
      article={resource.data || undefined}
    />
  );
}
