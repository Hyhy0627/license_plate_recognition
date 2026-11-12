export const API_BASE_URL = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export async function apiFetch(path: string, init: RequestInit = {}) {
  const response = await fetch(`${API_BASE_URL}${path}`, { ...init, credentials: "include", cache: "no-store" });
  if (response.status === 401 && !path.startsWith("/api/auth/")) {
    window.dispatchEvent(new Event("platesight:unauthorized"));
  }
  return response;
}

export async function apiError(response: Response, fallback: string) {
  const body = await response.json().catch(() => ({}));
  if (typeof body.detail === "string") return body.detail;
  return fallback;
}
