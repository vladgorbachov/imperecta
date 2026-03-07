/**
 * Auth context provider. Integrates with authStore (real API).
 * Exposes: isAuthenticated, user, login, logout.
 */

import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useState,
  type ReactNode,
} from "react";
import { useAuthStore } from "@/stores/authStore";

export interface AuthUser {
  name: string;
  email: string;
  plan: string;
  trialDaysLeft: number;
}

interface AuthContextValue {
  isAuthenticated: boolean;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

const AuthContext = createContext<AuthContextValue | null>(null);

function computeTrialDaysLeft(trialEndsAt: string | null): number {
  if (!trialEndsAt) return 0;
  const end = new Date(trialEndsAt);
  const now = new Date();
  return Math.max(0, Math.ceil((end.getTime() - now.getTime()) / (24 * 60 * 60 * 1000)));
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const authUser = useAuthStore((s) => s.user);
  const accessToken = useAuthStore((s) => s.accessToken);
  const loginStore = useAuthStore((s) => s.login);
  const logoutStore = useAuthStore((s) => s.logout);

  const [user, setUser] = useState<AuthUser | null>(null);

  useEffect(() => {
    if (authUser && accessToken) {
      setUser({
        name: authUser.name,
        email: authUser.email,
        plan: authUser.plan,
        trialDaysLeft: computeTrialDaysLeft(authUser.trial_ends_at),
      });
    } else {
      setUser(null);
    }
  }, [authUser, accessToken]);

  const login = useCallback(
    async (email: string, password: string, rememberMe = false) => {
      await loginStore({ email, password, remember_me: rememberMe });
    },
    [loginStore]
  );

  const logout = useCallback(() => {
    logoutStore();
    window.location.href = "/login";
  }, [logoutStore]);

  const value: AuthContextValue = {
    isAuthenticated: !!accessToken,
    user,
    login,
    logout,
  };

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
