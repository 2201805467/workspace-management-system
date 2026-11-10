import { useEffect, useState } from "react";
import { api, errorMessage } from "../api";
import type { User } from "../api";
import { useResource } from "../hooks/useResource";
import { downloadFile, fileTypes, formatBytes } from "../files";
import type { ProjectFile } from "../files";
import { formatDate, queryString } from "../work";
import type { Page, Person, Project } from "../work";
import { Empty, ErrorBox, Loading, Pager } from "./WorkUI";
import { FileUpload } from "./FileUpload";

function FileIndexStatus({ id, admin }: { id: string; admin: boolean }) {
  const resource = useResource<{
    indexing_status: string;
    error_code: string | null;
    has_text: boolean;
  }>(`/files/${id}/index`);
  const [error, setError] = useState(""),
    [busy, setBusy] = useState(false);
  useEffect(() => {
    if (
      resource.data &&
      ["pending", "processing"].includes(resource.data.indexing_status)
    ) {
      const timer = window.setTimeout(resource.reload, 3000);
      return () => window.clearTimeout(timer);
    }
  }, [resource.data, resource.reload]);
  async function retry() {
    setBusy(true);
    setError("");
    try {
      await api(`/files/${id}/reindex`, "POST");
      resource.reload();
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusy(false);
    }
  }
  const state = resource.data?.indexing_status;
  return (
    <div className="index-status">
      <p className="muted">
        حالة البحث في الوثيقة:{" "}
        {state === "ready"
          ? resource.data?.has_text
            ? "المحتوى جاهز للبحث"
            : "الاسم جاهز للبحث؛ لا يوجد نص مستخرج"
          : state === "failed"
            ? "تعذر استخراج النص؛ يبقى الملف الأصلي محفوظًا"
            : state === "processing"
              ? "جارٍ استخراج النص"
              : state === "pending"
                ? "بانتظار الفهرسة"
                : "جارٍ التحقق…"}
      </p>
      {admin && state === "failed" && (
        <button disabled={busy} onClick={() => void retry()}>
          إعادة محاولة الفهرسة
        </button>
      )}
      <ErrorBox error={error || resource.error} retry={resource.reload} />
    </div>
  );
}

export function ProjectFiles({
  user,
  project,
}: {
  user: User;
  project: Project;
}) {
  const [filters, setFilters] = useState({
    q: "",
    type: "",
    uploaded_by: "",
    sort_by: "created_at",
    sort_order: "desc",
    page: 1,
    page_size: 20,
  });
  const [search, setSearch] = useState("");
  const [error, setError] = useState("");
  const [notice, setNotice] = useState("");
  const [busyId, setBusyId] = useState("");
  const [uploading, setUploading] = useState(false);
  const [details, setDetails] = useState<ProjectFile | null>(null);
  const resource = useResource<Page<ProjectFile>>(
    `/projects/${project.id}/files?${queryString(filters)}`,
  );
  const uploaders = useResource<Person[]>(
    `/projects/${project.id}/file-uploaders`,
  );
  const update = (key: string, value: string | number) =>
    setFilters((previous) => ({ ...previous, [key]: value, page: 1 }));
  async function action(
    file: ProjectFile,
    kind: "download" | "delete" | "info",
  ) {
    if (
      kind === "delete" &&
      !window.confirm(
        `حذف الملف «${file.original_name}»؟ سيختفي من القائمة ولن يمكن تنزيله.`,
      )
    )
      return;
    setBusyId(file.id);
    setError("");
    setNotice("");
    try {
      if (kind === "download") {
        await downloadFile(file);
        setNotice("اكتمل تنزيل الملف.");
      } else if (kind === "info")
        setDetails(await api<ProjectFile>(`/files/${file.id}`));
      else {
        await api(`/files/${file.id}`, "DELETE");
        resource.reload();
        uploaders.reload();
        if (details?.id === file.id) setDetails(null);
        setNotice("تم حذف الملف من الوثائق المتاحة.");
      }
    } catch (error) {
      setError(errorMessage(error));
    } finally {
      setBusyId("");
    }
  }
  return (
    <section className="project-files">
      <div className="section-heading">
        <div>
          <span className="eyebrow">وثائق العمل</span>
          <h2>ملفات المشروع</h2>
          <p className="muted">
            ارفع الوثائق وشاركها مع أعضاء المشروع المخوّلين.
          </p>
        </div>
        {!project.is_archived && (
          <button
            className="primary"
            onClick={() => setUploading((value) => !value)}
          >
            {uploading ? "إغلاق الرفع" : "+ رفع ملف"}
          </button>
        )}
      </div>
      {project.is_archived && (
        <p className="notice">
          المشروع مؤرشف. الملفات متاحة للقراءة والتنزيل فقط.
        </p>
      )}
      {uploading && !project.is_archived && (
        <FileUpload
          projectId={project.id}
          onUploaded={() => {
            setFilters((previous) => ({ ...previous, page: 1 }));
            resource.reload();
            uploaders.reload();
            setError("");
            setNotice("تم رفع الملف بنجاح.");
          }}
        />
      )}
      <section className="card filters">
        <form
          className="search-row"
          onSubmit={(event) => {
            event.preventDefault();
            update("q", search);
          }}
        >
          <label className="sr-only" htmlFor="file-search">
            البحث عن ملف
          </label>
          <input
            id="file-search"
            placeholder="ابحث باسم الملف…"
            maxLength={255}
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
          <button>بحث في الملفات</button>
        </form>
        <div className="filter-grid">
          <label>
            نوع الملف
            <select
              aria-label="نوع الملف"
              value={filters.type}
              onChange={(event) => update("type", event.target.value)}
            >
              <option value="">كل الأنواع</option>
              {Object.entries(fileTypes).map(([value, label]) => (
                <option key={value} value={value}>
                  {label}
                </option>
              ))}
            </select>
          </label>
          <label>
            رفع بواسطة
            <select
              aria-label="رفع بواسطة"
              value={filters.uploaded_by}
              onChange={(event) => update("uploaded_by", event.target.value)}
            >
              <option value="">كل المستخدمين</option>
              {uploaders.data?.map((person) => (
                <option key={person.id} value={person.id}>
                  {person.name}
                </option>
              ))}
            </select>
          </label>
          <label>
            ترتيب الملفات
            <select
              aria-label="ترتيب الملفات"
              value={filters.sort_by}
              onChange={(event) => update("sort_by", event.target.value)}
            >
              <option value="created_at">تاريخ الرفع</option>
              <option value="original_name">الاسم</option>
              <option value="size_bytes">الحجم</option>
            </select>
          </label>
          <label>
            اتجاه ترتيب الملفات
            <select
              aria-label="اتجاه ترتيب الملفات"
              value={filters.sort_order}
              onChange={(event) => update("sort_order", event.target.value)}
            >
              <option value="desc">تنازلي</option>
              <option value="asc">تصاعدي</option>
            </select>
          </label>
        </div>
      </section>
      <ErrorBox error={error} />
      <ErrorBox error={resource.error} retry={resource.reload} />
      <ErrorBox error={uploaders.error} retry={uploaders.reload} />
      {notice && (
        <p className="notice" role="status">
          {notice}
        </p>
      )}
      {resource.loading && <Loading />}
      {resource.data && (
        <>
          {resource.data.items.length ? (
            <div className="card table-scroll files-table">
              <table>
                <thead>
                  <tr>
                    <th>الملف</th>
                    <th>النوع</th>
                    <th>الحجم</th>
                    <th>رفع بواسطة</th>
                    <th>تاريخ الرفع</th>
                    <th>الإجراءات</th>
                  </tr>
                </thead>
                <tbody>
                  {resource.data.items.map((file) => (
                    <tr key={file.id}>
                      <td>
                        <button
                          className="text-button file-name"
                          disabled={Boolean(busyId)}
                          onClick={() => void action(file, "info")}
                        >
                          {file.original_name}
                        </button>
                      </td>
                      <td>
                        <span className="file-type">
                          {file.extension.toUpperCase()}
                        </span>
                      </td>
                      <td dir="ltr">{formatBytes(file.size_bytes)}</td>
                      <td>{file.uploader.name}</td>
                      <td>{formatDate(file.created_at)}</td>
                      <td>
                        <div className="row-actions">
                          <button
                            disabled={Boolean(busyId)}
                            onClick={() => void action(file, "download")}
                          >
                            {busyId === file.id ? "جارٍ المعالجة…" : "تنزيل"}
                          </button>
                          {!project.is_archived &&
                            (user.role !== "Employee" ||
                              file.uploaded_by === user.id) && (
                              <button
                                className="danger-text"
                                disabled={Boolean(busyId)}
                                onClick={() => void action(file, "delete")}
                              >
                                حذف الملف
                              </button>
                            )}
                        </div>
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          ) : (
            <Empty>
              لا توجد وثائق تطابق البحث. يمكنك رفع أول ملف إذا كان المشروع غير
              مؤرشف.
            </Empty>
          )}
          <Pager
            result={resource.data}
            onPage={(page) => setFilters((previous) => ({ ...previous, page }))}
            onSize={(size) => update("page_size", size)}
          />
        </>
      )}
      {details && (
        <section className="card file-details">
          <div className="section-heading">
            <h3>معلومات الملف</h3>
            <button onClick={() => setDetails(null)}>إغلاق المعلومات</button>
          </div>
          <FileIndexStatus
            key={details.id}
            id={details.id}
            admin={user.role === "Admin"}
          />
          <h3 className="file-name">{details.original_name}</h3>
          <dl className="detail-grid">
            <div>
              <dt>نوع الملف</dt>
              <dd>{details.extension.toUpperCase()}</dd>
            </div>
            <div>
              <dt>الحجم</dt>
              <dd>{formatBytes(details.size_bytes)}</dd>
            </div>
            <div>
              <dt>رفع بواسطة</dt>
              <dd>{details.uploader.name}</dd>
            </div>
            <div>
              <dt>تاريخ الرفع</dt>
              <dd>{formatDate(details.created_at)}</dd>
            </div>
          </dl>
        </section>
      )}
    </section>
  );
}
