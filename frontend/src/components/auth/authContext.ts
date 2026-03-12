/**
 * Auth context and hook. AuthProvider wraps the app and provides the value.
 */

import { createContext, useContext } from "react";

export interface AuthUser {
  name: string;
  email: string;
  plan: string;
  trialDaysLeft: number;
}

export interface AuthContextValue {
  isAuthenticated: boolean;
  user: AuthUser | null;
  login: (email: string, password: string) => Promise<void>;
  logout: () => void;
}

export const AuthContext = createContext<AuthContextValue | null>(null);

export function useAuth(): AuthContextValue {
  const ctx = useContext(AuthContext);
  if (!ctx) {
    throw new Error("useAuth must be used within AuthProvider");
  }
  return ctx;
}
