import { createContext, ReactNode, useCallback, useContext, useEffect, useState } from "react";
import { api, hasToken, setToken, setUnauthorizedHandler } from "./api";
import type { User } from "./types";

interface RegisterData { username: string; password: string; email?: string; first_name?: string; last_name?: string }
interface AuthState {
  user: User | null;
  ready: boolean;
  login: (username: string, password: string) => Promise<void>;
  register: (data: RegisterData) => Promise<void>;
  logout: () => Promise<void>;
  setUser: (u: User) => void;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setUnauthorizedHandler(() => { setToken(null); setUser(null); });
    if (!hasToken()) { setReady(true); return; }
    api<User>("/auth/me").then(setUser).catch(() => setToken(null)).finally(() => setReady(true));
    return () => setUnauthorizedHandler(null);
  }, []);

  const login = useCallback(async (username: string, password: string) => {
    const res = await api<{ token: string; user: User }>("/auth/login", { method: "POST", body: { username, password } });
    setToken(res.token);
    setUser(res.user);
  }, []);

  const register = useCallback(async (data: RegisterData) => {
    const res = await api<{ token: string; user: User }>("/auth/register", { method: "POST", body: data });
    setToken(res.token);
    setUser(res.user);
  }, []);

  const logout = useCallback(async () => {
    try { await api("/auth/logout", { method: "POST" }); } catch {}
    setToken(null);
    setUser(null);
  }, []);

  return <Ctx.Provider value={{ user, ready, login, register, logout, setUser }}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const v = useContext(Ctx);
  if (!v) throw new Error("useAuth вне AuthProvider");
  return v;
}
