"use client";

import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";
import { LoaderCircle, LogOut } from "lucide-react";
import { apiError, apiFetch } from "../lib/api";

type User = { id: number; name: string; email: string };
type AuthState = { user: User | null; status: "loading" | "authenticated" | "anonymous" | "error" };
type AuthContextValue = AuthState & { refresh: () => Promise<void> };
const AuthContext = createContext<AuthContextValue | null>(null);

export function AuthProvider({ children }: { children: React.ReactNode }) {
  const [state, setState] = useState<AuthState>({ user: null, status: "loading" });
  const refresh = useCallback(async () => {
    try {
      const response = await apiFetch("/api/auth/me");
      if (response.status === 401) { setState({ user: null, status: "anonymous" }); return; }
      if (!response.ok) throw new Error("Không tải được tài khoản");
      const data = await response.json();
      setState({ user: data.user, status: "authenticated" });
    } catch { setState({ user: null, status: "error" }); }
  }, []);
  useEffect(() => {
    // Synchronize the session with the API, including logout in another tab.
    // eslint-disable-next-line react-hooks/set-state-in-effect
    void refresh();
    const expired = () => setState({ user: null, status: "anonymous" });
    const visible = () => { if (document.visibilityState === "visible") void refresh(); };
    const restored = () => { void refresh(); };
    window.addEventListener("platesight:unauthorized", expired);
    window.addEventListener("pageshow", restored);
    document.addEventListener("visibilitychange", visible);
    return () => {
      window.removeEventListener("platesight:unauthorized", expired);
      window.removeEventListener("pageshow", restored);
      document.removeEventListener("visibilitychange", visible);
    };
  }, [refresh]);
  return <AuthContext.Provider value={{ ...state, refresh }}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const value = useContext(AuthContext);
  if (!value) throw new Error("AuthProvider is required");
  return value;
}

export function RequireAuth({ children }: { children: React.ReactNode }) {
  const { user, status, refresh } = useAuth();
  const pathname = usePathname();
  const router = useRouter();
  useEffect(() => {
    if (status === "anonymous") router.replace(`/login?next=${pathname === "/history" ? "/history" : "/"}`);
  }, [status, pathname, router]);
  if (status === "error") return <div className="session-state" role="alert"><h1>Chưa kết nối được máy chủ</h1><p>Không thể kiểm tra phiên đăng nhập. Vui lòng thử lại.</p><button onClick={() => void refresh()}>Thử lại</button></div>;
  if (!user) return <div className="session-state" role="status"><LoaderCircle className="animate-spin" aria-hidden="true" /><p>Đang kiểm tra phiên đăng nhập…</p></div>;
  return <div key={user.id}>{children}</div>;
}

export function AccountMenu() {
  const { user } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  async function logout() {
    setBusy(true); setError("");
    try {
      const response = await apiFetch("/api/auth/logout", { method: "POST" });
      if (!response.ok) throw new Error(await apiError(response, "Chưa đăng xuất được. Hãy thử lại."));
      // Drop cached client pages and image results when changing accounts.
      window.location.replace("/login");
    } catch (reason) { setError(reason instanceof Error ? reason.message : "Không thể kết nối máy chủ."); setBusy(false); }
  }
  if (!user) return null;
  return <div className="account-menu"><div className="account-avatar" aria-hidden="true">{user.name.charAt(0).toUpperCase()}</div><span className="account-name" title={user.email}>{user.name}</span><button type="button" onClick={logout} disabled={busy} aria-label="Đăng xuất" title="Đăng xuất"><LogOut size={17} aria-hidden="true" /><span>{busy ? "Đang thoát…" : "Đăng xuất"}</span></button>{error && <p role="alert" className="account-error">{error}</p>}</div>;
}
