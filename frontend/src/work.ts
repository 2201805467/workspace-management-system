import type { Role } from "./api";

export interface Person {
  id: string;
  name: string;
  email: string;
  role: Role;
  is_active: boolean;
}
export type ProjectStatus =
  "Planning" | "Active" | "On Hold" | "Completed" | "Cancelled";
export type TaskStatus = "todo" | "in_progress" | "blocked" | "done";
export type Priority = "low" | "medium" | "high" | "urgent";
export interface Project {
  id: string;
  name: string;
  description: string | null;
  manager_id: string;
  created_by: string;
  manager: Person;
  status: ProjectStatus;
  start_date: string | null;
  end_date: string | null;
  is_archived: boolean;
  archived_at: string | null;
  created_at: string;
  updated_at: string;
}
export interface Member {
  id: string;
  project_id: string;
  user_id: string;
  joined_at: string;
  user: Person;
}
export interface Task {
  id: string;
  project_id: string;
  project_name: string;
  project_archived: boolean;
  title: string;
  description: string | null;
  assigned_to: string;
  assignee: Person;
  created_by: string;
  creator: Person;
  status: TaskStatus;
  priority: Priority;
  due_date: string | null;
  created_at: string;
  updated_at: string;
  completed_at: string | null;
  is_overdue: boolean;
}
export interface Page<T> {
  items: T[];
  page: number;
  page_size: number;
  total: number;
  total_pages: number;
}

export const projectStatuses: Record<ProjectStatus, string> = {
  Planning: "قيد التخطيط",
  Active: "نشط",
  "On Hold": "معلّق",
  Completed: "مكتمل",
  Cancelled: "ملغى",
};
export const taskStatuses: Record<TaskStatus, string> = {
  todo: "لم تبدأ",
  in_progress: "قيد التنفيذ",
  blocked: "متوقفة",
  done: "مكتملة",
};
export const priorities: Record<Priority, string> = {
  low: "منخفضة",
  medium: "متوسطة",
  high: "مرتفعة",
  urgent: "عاجلة",
};
export const canEdit = (user: { id: string; role: Role }, project: Project) =>
  !project.is_archived &&
  (user.role === "Admin" ||
    (user.role === "Manager" && project.manager_id === user.id));
export const formatDate = (value: string | null) =>
  value
    ? new Intl.DateTimeFormat("ar-LY", {
        dateStyle: "medium",
        timeZone: "Africa/Tripoli",
      }).format(new Date(value.length === 10 ? value + "T12:00:00Z" : value))
    : "غير محدد";
export function queryString(
  values: Record<string, string | number | boolean | undefined>,
) {
  return new URLSearchParams(
    Object.entries(values)
      .filter(([, value]) => value !== "" && value !== undefined)
      .map(([key, value]) => [key, String(value)]),
  ).toString();
}
