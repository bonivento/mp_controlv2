"use client";

import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import { getStore, type AppUser } from "@/lib/data";
import { NOT_CONFIGURED } from "@/lib/env";

interface AuthState {
  /** undefined mientras se lee la sesión; null si no hay sesión. */
  user: AppUser | null | undefined;
}

const AuthContext = createContext<AuthState>({ user: undefined });

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<AppUser | null | undefined>(undefined);

  useEffect(() => {
    if (NOT_CONFIGURED) {
      const t = setTimeout(() => setUser(null), 0);
      return () => clearTimeout(t);
    }
    const store = getStore();
    let alive = true;
    store.auth.getUser().then(
      (u) => alive && setUser(u),
      () => alive && setUser(null),
    );
    const off = store.auth.onChange((u) => alive && setUser(u));
    return () => {
      alive = false;
      off();
    };
  }, []);

  return <AuthContext value={{ user }}>{children}</AuthContext>;
}

export const useAuth = () => useContext(AuthContext);
