import { useState } from "react";
import { useResource } from "../hooks/useResource";
import type { Page } from "../work";
import { ErrorBox } from "./WorkUI";

export function PagedChoice({
  path,
  label,
  value,
  onChange,
  empty = "الكل",
  initialLabel = "",
  required = false,
  disabled = false,
}: {
  path: string;
  label: string;
  value: string;
  onChange: (value: string) => void;
  empty?: string;
  initialLabel?: string;
  required?: boolean;
  disabled?: boolean;
}) {
  const [page, setPage] = useState(1);
  const [name, setName] = useState(initialLabel);
  const resource = useResource<Page<{ id: string; name: string }>>(
    `${path}${path.includes("?") ? "&" : "?"}page=${page}&page_size=20`,
  );
  return (
    <div className="paged-choice">
      <label>
        {label}
        <select
          aria-label={label}
          value={value}
          required={required}
          disabled={disabled || resource.loading}
          onChange={(event) => {
            setName(event.target.selectedOptions[0].textContent || "");
            onChange(event.target.value);
          }}
        >
          <option value="" disabled={required}>
            {empty}
          </option>
          {value && !resource.data?.items.some((item) => item.id === value) && (
            <option value={value}>
              {name || initialLabel || "الخيار المحدد"}
            </option>
          )}
          {resource.data?.items.map((item) => (
            <option key={item.id} value={item.id}>
              {item.name}
            </option>
          ))}
        </select>
      </label>
      {resource.data && resource.data.total_pages > 1 && (
        <div className="row-actions">
          <button
            type="button"
            disabled={disabled || page <= 1}
            onClick={() => setPage(page - 1)}
          >
            خيارات سابقة
          </button>
          <button
            type="button"
            disabled={disabled || page >= resource.data!.total_pages}
            onClick={() => setPage(page + 1)}
          >
            خيارات أخرى
          </button>
        </div>
      )}
      <ErrorBox error={resource.error} retry={resource.reload} />
    </div>
  );
}
