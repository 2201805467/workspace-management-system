import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { errorMessage } from "../api";
import { useResource } from "../hooks/useResource";
import { formatBytes, uploadFile } from "../files";
import type { FilePolicy } from "../files";
import { ErrorBox } from "./WorkUI";

export function FileUpload({
  projectId,
  onUploaded,
}: {
  projectId: string;
  onUploaded: () => void;
}) {
  const policy = useResource<FilePolicy>("/files/policy");
  const [file, setFile] = useState<File | null>(null);
  const [busy, setBusy] = useState(false);
  const [progress, setProgress] = useState(0);
  const [error, setError] = useState("");
  const controller = useRef<AbortController | null>(null);
  const input = useRef<HTMLInputElement>(null);
  useEffect(() => () => controller.current?.abort(), []);
  function validate(file: File) {
    const extension = file.name.split(".").pop()?.toLowerCase() || "";
    const types = policy.data?.allowed_types || {
      pdf: "application/pdf",
      png: "image/png",
      jpg: "image/jpeg",
      jpeg: "image/jpeg",
      docx: "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    };
    if (!types[extension]) return "اختر ملف PDF أو PNG أو JPEG أو DOCX.";
    if (file.size === 0) return "الملف فارغ.";
    if (file.size > (policy.data?.max_size_bytes || 10 * 1024 * 1024))
      return "حجم الملف أكبر من الحد المسموح.";
    if (
      file.type &&
      file.type !== types[extension] &&
      file.type !== "application/octet-stream" &&
      !(extension === "docx" && file.type === "application/zip")
    )
      return "نوع الملف المعلن لا يتطابق مع امتداده.";
    return "";
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (busy || !file) return;
    const invalid = validate(file);
    if (invalid) {
      setError(invalid);
      return;
    }
    setBusy(true);
    setError("");
    setProgress(0);
    const active = new AbortController();
    controller.current = active;
    try {
      await uploadFile(projectId, file, setProgress, active.signal);
      setFile(null);
      if (input.current) input.current.value = "";
      onUploaded();
    } catch (error) {
      if (!active.signal.aborted) setError(errorMessage(error));
    } finally {
      controller.current = null;
      setBusy(false);
    }
  }
  return (
    <section className="card file-upload">
      <h3>رفع وثيقة جديدة</h3>
      <p className="muted">
        PDF، صور PNG وJPEG، ومستندات Word. الحد الأقصى{" "}
        {formatBytes(policy.data?.max_size_bytes || 10 * 1024 * 1024)}.
      </p>
      <form onSubmit={submit}>
        <label htmlFor="project-file">اختر ملفًا</label>
        <input
          ref={input}
          id="project-file"
          type="file"
          accept=".pdf,.png,.jpg,.jpeg,.docx"
          disabled={busy || policy.loading}
          onChange={(event) => {
            const chosen = event.target.files?.[0] || null;
            setFile(chosen);
            setError(chosen ? validate(chosen) : "");
          }}
        />
        {file && (
          <p className="selected-file">
            <strong>{file.name}</strong>
            <span>
              {formatBytes(file.size)} ·{" "}
              {file.name.split(".").pop()?.toUpperCase()}
            </span>
          </p>
        )}
        {busy && (
          <div className="upload-progress" role="status">
            <progress aria-label="تقدم رفع الملف" value={progress} max={100} />
            <span>
              {progress < 100
                ? `جارٍ الرفع… ${progress}%`
                : "اكتمل الإرسال، جارٍ التحقق وحفظ الملف…"}
            </span>
          </div>
        )}
        <ErrorBox error={policy.error} retry={policy.reload} />
        <ErrorBox error={error} />
        <div className="row-actions">
          <button
            className="primary"
            disabled={
              busy ||
              !file ||
              Boolean(file && validate(file)) ||
              policy.loading ||
              Boolean(policy.error)
            }
          >
            {busy ? "جارٍ رفع الملف…" : "رفع الملف"}
          </button>
        </div>
      </form>
    </section>
  );
}
