import { ApiError } from "./api";
import type { Person } from "./work";

export interface ProjectFile {
  id: string;
  project_id: string;
  uploaded_by: string;
  uploader: Person;
  original_name: string;
  mime_type: string;
  extension: string;
  size_bytes: number;
  checksum: string;
  created_at: string;
}
export interface FilePolicy {
  max_size_bytes: number;
  allowed_types: Record<string, string>;
}
export const fileTypes: Record<string, string> = {
  pdf: "PDF",
  png: "PNG",
  jpg: "JPEG",
  docx: "Word",
};
export const formatBytes = (bytes: number) =>
  bytes >= 1024 * 1024
    ? `${(bytes / 1024 / 1024).toFixed(2)} MB`
    : `${(bytes / 1024).toFixed(1)} KB`;

function responseError(status: number, value: unknown): ApiError {
  if (status === 401) window.dispatchEvent(new Event("session-expired"));
  const data = value as { detail?: unknown } | null;
  return new ApiError(
    status,
    typeof data?.detail === "string"
      ? data.detail
      : status === 413
        ? "حجم الملف أكبر من الحد المسموح."
        : "تعذرت معالجة الملف. أعد المحاولة.",
  );
}

export function uploadFile(
  projectId: string,
  file: File,
  progress: (value: number) => void,
  signal: AbortSignal,
): Promise<ProjectFile> {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    const abort = () => xhr.abort();
    const cleanup = () => signal.removeEventListener("abort", abort);
    xhr.open("POST", `/api/projects/${projectId}/files`);
    xhr.setRequestHeader("X-Requested-With", "WorkSpace");
    xhr.responseType = "json";
    xhr.timeout = 120000;
    xhr.upload.onprogress = (event) => {
      if (event.lengthComputable)
        progress(Math.round((event.loaded / event.total) * 100));
    };
    xhr.onload = () => {
      cleanup();
      if (xhr.status === 201) resolve(xhr.response as ProjectFile);
      else reject(responseError(xhr.status, xhr.response));
    };
    xhr.onerror = () => {
      cleanup();
      reject(
        new Error("انقطع الاتصال أثناء الرفع. تحقق من الاتصال وحاول مجددًا."),
      );
    };
    xhr.ontimeout = () => {
      cleanup();
      reject(new Error("انتهت مهلة الرفع. أعد المحاولة."));
    };
    xhr.onabort = () => {
      cleanup();
      reject(new Error("تم إلغاء الرفع."));
    };
    signal.addEventListener("abort", abort, { once: true });
    if (signal.aborted) {
      cleanup();
      reject(new Error("تم إلغاء الرفع."));
      return;
    }
    const data = new FormData();
    data.append("file", file);
    xhr.send(data);
  });
}

export async function downloadFile(file: ProjectFile) {
  let response: Response;
  try {
    response = await fetch(`/api/files/${file.id}/download`, {
      credentials: "same-origin",
      cache: "no-store",
    });
  } catch {
    throw new Error("تعذر الاتصال لتنزيل الملف.");
  }
  if (!response.ok)
    throw responseError(
      response.status,
      await response.json().catch(() => null),
    );
  let blob: Blob;
  try {
    blob = await response.blob();
  } catch {
    throw new Error("انقطع تنزيل الملف قبل اكتماله. أعد المحاولة.");
  }
  if (blob.size !== file.size_bytes)
    throw new Error("لم يكتمل تنزيل الملف. حاول مجددًا.");
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = file.original_name;
  document.body.appendChild(anchor);
  anchor.click();
  anchor.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1000);
}
