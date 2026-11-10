import { useState } from "react";
import type { FormEvent } from "react";
import { Link } from "react-router-dom";
import { api, errorMessage } from "../api";
import { useResource } from "../hooks/useResource";
import type { Category } from "../knowledge";
import type { Page } from "../work";
import { queryString } from "../work";
import { Empty, ErrorBox, Loading, Pager } from "../components/WorkUI";

export function KnowledgeCategories() {
  const [filters, setFilters] = useState({
    q: "",
    sort: "title",
    page: 1,
    page_size: 20,
  });
  const [editing, setEditing] = useState<Category | "new" | null>(null);
  const [error, setError] = useState(""),
    [notice, setNotice] = useState(""),
    [busy, setBusy] = useState(false);
  const resource = useResource<Page<Category>>(
    `/knowledge/categories?${queryString(filters)}`,
  );
  async function save(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!editing) return;
    const data = Object.fromEntries(new FormData(event.currentTarget));
    if (!data.slug) delete data.slug;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(
        editing === "new"
          ? "/knowledge/categories"
          : `/knowledge/categories/${editing.id}`,
        editing === "new" ? "POST" : "PATCH",
        data,
      );
      setEditing(null);
      resource.reload();
      setNotice("تم حفظ التصنيف.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  async function remove(item: Category) {
    if (!window.confirm(`حذف التصنيف «${item.name}»؟`)) return;
    setBusy(true);
    setError("");
    setNotice("");
    try {
      await api(`/knowledge/categories/${item.id}`, "DELETE");
      resource.reload();
      setNotice("تم حذف التصنيف.");
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  return (
    <>
      <Link className="back-link" to="/knowledge">
        ← قاعدة المعرفة
      </Link>
      <div className="section-heading">
        <h1>تصنيفات المعرفة</h1>
        <button className="primary" onClick={() => setEditing("new")}>
          + تصنيف جديد
        </button>
      </div>
      <ErrorBox error={error} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {editing && (
        <section className="card editor">
          <h2>{editing === "new" ? "تصنيف جديد" : "تعديل التصنيف"}</h2>
          <form key={editing === "new" ? "new" : editing.id} onSubmit={save}>
            <div className="form-grid">
              <div>
                <label htmlFor="category-name">اسم التصنيف</label>
                <input
                  id="category-name"
                  name="name"
                  required
                  minLength={3}
                  maxLength={100}
                  defaultValue={editing === "new" ? "" : editing.name}
                />
              </div>
              <div>
                <label htmlFor="category-slug">المعرف النصي للتصنيف</label>
                <input
                  id="category-slug"
                  name="slug"
                  minLength={3}
                  maxLength={200}
                  defaultValue={editing === "new" ? "" : editing.slug}
                  placeholder="يُنشأ تلقائيًا إذا تركته فارغًا"
                />
              </div>
              <div className="span-all">
                <label htmlFor="category-description">وصف التصنيف</label>
                <textarea
                  id="category-description"
                  name="description"
                  maxLength={1000}
                  defaultValue={
                    editing === "new" ? "" : editing.description || ""
                  }
                />
              </div>
            </div>
            <div className="row-actions">
              <button className="primary" disabled={busy}>
                حفظ التصنيف
              </button>
              <button
                type="button"
                disabled={busy}
                onClick={() => setEditing(null)}
              >
                إلغاء
              </button>
            </div>
          </form>
        </section>
      )}
      <section className="card filters">
        <label>
          بحث في التصنيفات
          <input
            value={filters.q}
            maxLength={100}
            onChange={(event) =>
              setFilters({ ...filters, q: event.target.value, page: 1 })
            }
          />
        </label>
        <label>
          ترتيب التصنيفات
          <select
            aria-label="ترتيب التصنيفات"
            value={filters.sort}
            onChange={(event) =>
              setFilters({ ...filters, sort: event.target.value, page: 1 })
            }
          >
            <option value="title">الاسم</option>
            <option value="newest">الأحدث</option>
            <option value="oldest">الأقدم</option>
          </select>
        </label>
      </section>
      <ErrorBox error={resource.error} retry={resource.reload} />
      {resource.loading && <Loading />}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="card table-scroll">
              <table>
                <thead>
                  <tr>
                    <th>التصنيف</th>
                    <th>المعرف النصي</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {resource.data.items.map((item) => (
                    <tr key={item.id}>
                      <td>
                        {item.name}
                        <small>{item.description}</small>
                      </td>
                      <td>{item.slug}</td>
                      <td>
                        <div className="row-actions">
                          <button
                            disabled={busy}
                            onClick={() => setEditing(item)}
                          >
                            تعديل التصنيف
                          </button>
                          <button
                            disabled={busy}
                            className="danger-text"
                            onClick={() => void remove(item)}
                          >
                            حذف التصنيف
                          </button>
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>أنشئ أول تصنيف لتنظيم المقالات.</Empty>
          )}
          <Pager
            result={resource.data}
            onPage={(page) => setFilters({ ...filters, page })}
            onSize={(page_size) =>
              setFilters({ ...filters, page_size, page: 1 })
            }
          />
        </>
      )}
    </>
  );
}
