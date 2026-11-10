import type { Person } from "./work";
export interface Category {
  id: string;
  name: string;
  description: string | null;
  slug: string;
  created_at: string;
  updated_at: string;
}
export interface Article {
  id: string;
  title: string;
  slug: string;
  summary: string;
  content: string;
  category_id: string | null;
  project_id: string | null;
  category: Category | null;
  project_name: string | null;
  author: Person;
  author_id: string;
  status: "draft" | "published" | "archived";
  language: "ar" | "en";
  created_at: string;
  updated_at: string;
  published_at: string | null;
  archived_at: string | null;
  can_edit: boolean;
}
export interface SearchHit {
  id: string;
  type: "article" | "file";
  title: string;
  snippet: string;
  project_id: string | null;
  project_name: string | null;
  category_name: string | null;
  updated_at: string;
  relevance_score: number;
  match_kind: string;
}
export const articleStatuses = {
  draft: "مسودة",
  published: "منشور",
  archived: "مؤرشف",
};
