import { useCallback } from "react";

const ADMIN_API = import.meta.env.VITE_ADMIN_API_BASE_URL || "";

// Read token from zustand persisted store directly
function getAdminToken(): string | null {
  try {
    const raw = localStorage.getItem("jobaimer-admin-auth");
    if (!raw) return null;
    return JSON.parse(raw)?.state?.token ?? null;
  } catch {
    return null;
  }
}

export async function adminFetch(path: string, options: RequestInit = {}): Promise<any> {
  const token = getAdminToken();
  const res = await fetch(`${ADMIN_API}${path}`, {
    ...options,
    headers: {
      "Content-Type": "application/json",
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...(options.headers ?? {}),
    },
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.detail || `HTTP ${res.status}`);
  }
  return res.json();
}

export function useAdminFetch() {
  return useCallback((path: string, options?: RequestInit) => adminFetch(path, options), []);
}
