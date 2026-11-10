import { useState } from "react";
import { Link, useParams } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useResource } from "../hooks/useResource";
import type { Article } from "../knowledge";
import { articleStatuses } from "../knowledge";
import { formatDate } from "../work";
import { ErrorBox, Loading } from "../components/WorkUI";
import { Markdown } from "../components/Markdown";

export function ArticleDetails() {
  const { articleId } = useParams();
  const resource = useResource<Article>(`/knowledge/articles/${articleId}`);
  const [busy, setBusy] = useState(false),
    [error, setError] = useState(""),
    [notice, setNotice] = useState("");
  async function transition(action: string) {
    if (
      action === "archive" &&
      !window.confirm("أرشفة المقال وإزالته من البحث العام؟")
    )
      return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/knowledge/articles/${articleId}/${action}`, "POST");
      resource.reload();
      setNotice(action === "publish" ? "تم نشر المقال." : "تمت أرشفة المقال.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  if (resource.loading) return <Loading />;
  if (resource.error)
    return <ErrorBox error={resource.error} retry={resource.reload} />;
  if (!resource.data) return null;
  const article = resource.data;
  return (
    <>
      <Link className="back-link" to="/knowledge">
        ← قاعدة المعرفة
      </Link>
      <div className="section-heading">
        <div>
          <span className="eyebrow">
            {article.category?.name || "معرفة الشركة"}
          </span>
          <h1 dir={article.language === "en" ? "ltr" : "rtl"}>
            {article.title}
          </h1>
          <span className="pill">{articleStatuses[article.status]}</span>
        </div>
        {article.can_edit && article.status !== "archived" && (
          <div className="row-actions">
            <Link className="button-link" to={`/knowledge/${article.id}/edit`}>
              تعديل المقال
            </Link>
            {article.status === "draft" && (
              <button
                className="primary"
                disabled={busy}
                onClick={() => void transition("publish")}
              >
                نشر المقال
              </button>
            )}
            <button
              className="danger-text"
              disabled={busy}
              onClick={() => void transition("archive")}
            >
              أرشفة المقال
            </button>
          </div>
        )}
      </div>
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      <section className="card article-body">
        <p className="article-lede">{article.summary}</p>
        <div className="article-byline">
          <span>{article.author.name}</span>
          <span>آخر تحديث: {formatDate(article.updated_at)}</span>
          <span>الإنشاء: {formatDate(article.created_at)}</span>
          {article.published_at && (
            <span>النشر: {formatDate(article.published_at)}</span>
          )}
        </div>
        {article.project_id ? (
          <p>
            <Link to={`/projects/${article.project_id}`}>
              المشروع: {article.project_name}
            </Link>
          </p>
        ) : (
          <p className="muted">عام على مستوى الشركة</p>
        )}
        <div dir={article.language === "en" ? "ltr" : "rtl"}>
          <Markdown content={article.content} />
        </div>
      </section>
    </>
  );
}
