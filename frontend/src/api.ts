export type Role = "Admin" | "Manager" | "Employee";
export interface User {
  id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
  created_at: string;
}

export class ApiError extends Error {
  status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

export async function api<T>(
  path: string,
  method = "GET",
  body?: unknown,
  notifyExpired = true,
): Promise<T> {
  let response: Response;
  try {
    response = await fetch(`/api${path}`, {
      method,
      credentials: "same-origin",
      headers: {
        "Content-Type": "application/json",
        "X-Requested-With": "WorkSpace",
      },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    throw new ApiError(
      0,
      "تعذر الاتصال بالخادم. تحقق من تشغيل الخدمات ثم أعد المحاولة.",
    );
  }
  if (!response.ok) {
    const data = await response.json().catch(() => null);
    if (notifyExpired && response.status === 401 && path !== "/auth/login")
      window.dispatchEvent(new Event("session-expired"));
    throw new ApiError(
      response.status,
      typeof data?.detail === "string"
        ? data.detail
        : response.status === 422
          ? "تحقق من الحقول المطلوبة وصحة القيم والتواريخ."
          : "حدث خطأ في الخادم. حاول مرة أخرى.",
    );
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export const roleLabels: Record<Role, string> = {
  Admin: "مسؤول النظام",
  Manager: "مدير",
  Employee: "موظف",
};

export const errorMessage = (error: unknown) =>
  error instanceof Error ? error.message : "حدث خطأ غير متوقع";
