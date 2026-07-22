"use client";
/**
 * Auth state for the whole app. Firebase handles Google sign-in;
 * on first sign-in we call api.syncUser() so a row exists in Postgres.
 */
import { createContext, useContext, useEffect, useState, type ReactNode } from "react";
import type { User } from "firebase/auth";
import { watchAuth, signInWithGoogle, signOut, firebaseEnabled } from "@/lib/firebase";
import { api } from "@/lib/api";

interface AuthState {
  user: User | null;
  loading: boolean;
  enabled: boolean;
  login: () => Promise<void>;
  logout: () => Promise<void>;
}

const AuthCtx = createContext<AuthState>({
  user: null,
  loading: true,
  enabled: false,
  login: async () => {},
  logout: async () => {},
});
export const useAuth = () => useContext(AuthCtx);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    const unsub = watchAuth((u) => {
      setUser(u);
      setLoading(false);
      if (u) api.syncUser().catch(() => {}); // backend offline is fine during frontend-only dev
    });
    return unsub;
  }, []);

  return (
    <AuthCtx.Provider
      value={{
        user,
        loading,
        enabled: firebaseEnabled,
        login: async () => {
          await signInWithGoogle();
        },
        logout: async () => {
          await signOut();
        },
      }}
    >
      {children}
    </AuthCtx.Provider>
  );
}
