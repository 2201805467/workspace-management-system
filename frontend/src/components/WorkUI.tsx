import type { ReactNode } from "react";
import type { Page } from "../work";

export function ErrorBox({
  error,
  retry,
}: {
  error: string;
  retry?: () => void;
}) {
  return error ? (
    <div className="error" role="alert">
      {error}{" "}
      {retry && (
        <button type="button" onClick={retry}>
          إعادة المحاولة
        </button>
      )}
    </div>
  ) : null;
}
export function Loading() {
  return (
    <p className="loading-inline" role="status">
      جارٍ تحميل البيانات…
    </p>
  );
}
export function Empty({ children }: { children: ReactNode }) {
  return (
    <div className="empty-state">
      <span aria-hidden="true">◇</span>
      <h2>لا توجد نتائج</h2>
      <p className="muted">{children}</p>
    </div>
  );
}
export function Pager<T>({
  result,
  onPage,
  onSize,
}: {
  result: Page<T>;
  onPage: (page: number) => void;
  onSize: (size: number) => void;
}) {
  return (
    <div className="pager">
      <span>
        {result.total} نتيجة · الصفحة {result.page} من {result.total_pages || 1}
      </span>
      <div className="row-actions">
        <button
          disabled={result.page <= 1}
          onClick={() => onPage(result.page - 1)}
        >
          السابق
        </button>
        <button
          disabled={result.page >= result.total_pages}
          onClick={() => onPage(result.page + 1)}
        >
          التالي
        </button>
        <label>
          في الصفحة
          <select
            value={result.page_size}
            onChange={(event) => onSize(Number(event.target.value))}
          >
            {[10, 20, 50, 100].map((size) => (
              <option key={size}>{size}</option>
            ))}
          </select>
        </label>
      </div>
    </div>
  );
}
