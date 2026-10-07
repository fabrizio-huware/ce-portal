import { createContext, useCallback, useContext, useEffect, useMemo, useState, type ReactNode } from "react";

import { api, unwrap } from "../api/client";
import { authStore } from "../api/authStore";
import type { UserOut } from "../api/types";

type State =
  | { status: "loading" }
  | { status: "anon"; expired: boolean }
  | { status: "authed"; user: UserOut };

type Ctx = {
  state: State;
  user: UserOut | null;
  isEditor: boolean; // admin o presale: vedono costi e margini
  isAdmin: boolean;
  signIn: (token: string, user: UserOut) => void;
  signOut: () => void;
};

const AuthContext = createContext<Ctx | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [state, setState] = useState<State>(() => (authStore.getToken() ? { status: "loading" } : { status: "anon", expired: false }));

  // All'avvio, se c'è un token lo si convalida: ruolo e stato dell'utente li decide sempre il server.
  useEffect(() => {
    if (state.status !== "loading") return;
    let cancelled = false;
    api.GET("/api/v1/auth/me").then((result) => {
      if (cancelled) return;
      try {
        setState({ status: "authed", user: unwrap(result) });
      } catch {
        authStore.clear();
        setState({ status: "anon", expired: true });
      }
    });
    return () => {
      cancelled = true;
    };
  }, [state.status]);

  useEffect(() => authStore.subscribe(() => setState({ status: "anon", expired: true })), []);

  const signIn = useCallback((token: string, user: UserOut) => {
    authStore.setToken(token);
    setState({ status: "authed", user });
  }, []);
  const signOut = useCallback(() => {
    authStore.clear();
    setState({ status: "anon", expired: false });
  }, []);

  const value = useMemo<Ctx>(() => {
    const user = state.status === "authed" ? state.user : null;
    return {
      state, user, signIn, signOut,
      isEditor: user?.role === "admin" || user?.role === "presale",
      isAdmin: user?.role === "admin",
    };
  }, [state, signIn, signOut]);

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): Ctx {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth va usato dentro AuthProvider");
  return ctx;
}
