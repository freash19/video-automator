import { clsx, type ClassValue } from "clsx";
import { twMerge } from "tailwind-merge";

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL || "http://127.0.0.1:8000";

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs));
}

export function projectStatusRu(status: unknown): string {
  const s = String(status || "").toLowerCase();
  if (s === "pending") return "В ожидании";
  if (s === "running") return "В работе";
  if (s === "completed") return "Завершён";
  if (s === "failed") return "Ошибка";
  return String(status || "");
}

export function formatDateTimeRu(iso: unknown): string {
  const v = String(iso || "").trim();
  if (!v) return "";
  const d = new Date(v);
  if (Number.isNaN(d.getTime())) return v;
  return d.toLocaleString();
}
