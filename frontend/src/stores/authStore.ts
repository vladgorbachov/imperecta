import { create } from "zustand";
import i18n from "i18next";
import { authApi } from "@/api/auth";
import { setAuthCookie } from "@/lib/authCookie";
import {
  loadTokens,
  saveTokens,
  clearStoredTokens,
  getStoredToken,
} from "@/lib/authStorage";

const LANGUAGE_STORAGE_KEY = "imperecta_language";

function applyUserLanguage(language: string): void {
  i18n.changeLanguage(language);
  localStorage.setItem(LANGUAGE_STORAGE_KEY, language);
}

export interface User {
  id: string;
  email: string;
  name: string;
  company_name: string | null;
  plan: string;
  trial_ends_at: string | null;
  language: string;
  created_at: string;
  telegram_chat_id?: number | null;
  avatar_url?: string | null;
  is_superuser?: boolean;
  force_password_change?: boolean;
}

export interface LoginCredentials {
  email: string;
  password: string;
  remember_me: boolean;
}

export interface LoginResult {
  success: boolean;
  forcePasswordChange?: boolean;
}

export { clearStoredTokens, getStoredToken };

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  persistent: boolean;
  expiresAt: string | null;
  isInitialized: boolean;

  login: (credentials: LoginCredentials) => Promise<LoginResult>;
  register: (
    email: string,
    password: string,
    name: string,
    companyName?: string,
    language?: string
  ) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
  setTokensFromResponse: (data: {
    access_token: string;
    refresh_token: string;
    persistent?: boolean;
    expires_at?: string;
  }) => void;
  fetchUser: () => Promise<User | null>;
  refreshAccessToken: () => Promise<boolean>;
  restoreSession: () => Promise<boolean>;
  checkSessionExpiry: () => { valid: boolean; nearExpiry?: boolean };
  updateLanguage: (code: string) => Promise<void>;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: null,
  refreshToken: null,
  persistent: false,
  expiresAt: null,
  isInitialized: false,

  login: async (credentials: LoginCredentials) => {
    const { data } = await authApi.login(
      credentials.email,
      credentials.password,
      credentials.remember_me
    );
    const persistent = data.persistent ?? credentials.remember_me;
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt: data.expires_at ?? null,
    });
    saveTokens({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt: data.expires_at ?? null,
      user: null as unknown,
    });
    setAuthCookie(persistent);
    const user = await get().fetchUser();
    if (user) {
      if (data.force_password_change !== undefined) {
        set({ user: { ...user, force_password_change: data.force_password_change } });
      }
      saveTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        persistent,
        expiresAt: data.expires_at ?? null,
        user: { ...user, force_password_change: data.force_password_change } as User,
      });
      setAuthCookie(persistent);
      if (user.language) applyUserLanguage(user.language);
    }
    return {
      success: true,
      forcePasswordChange: data.force_password_change ?? false,
    };
  },

  register: async (
    email: string,
    password: string,
    name: string,
    companyName?: string,
    language?: string
  ) => {
    const { data } = await authApi.register(
      email,
      password,
      name,
      companyName,
      language
    );
    const persistent = data.persistent ?? false;
    const expiresAt = data.expires_at ?? null;
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt,
    });
    saveTokens({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt,
      user: null as unknown,
    });
    setAuthCookie(persistent);
    await get().fetchUser();
  },

  logout: () => {
    clearStoredTokens();
    set({
      user: null,
      accessToken: null,
      refreshToken: null,
      persistent: false,
      expiresAt: null,
    });
    window.location.href = "/login";
  },

  setUser: (user) => set({ user }),

  setTokensFromResponse: (data: {
    access_token: string;
    refresh_token: string;
    persistent?: boolean;
    expires_at?: string;
  }) => {
    const persistent = data.persistent ?? false;
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt: data.expires_at ?? null,
    });
    saveTokens({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
      persistent,
      expiresAt: data.expires_at ?? null,
      user: get().user as unknown,
    });
    setAuthCookie(persistent);
  },

  fetchUser: async () => {
    const token = get().accessToken ?? getStoredToken();
    if (!token) return null;
    try {
      const { data } = await authApi.getMe();
      set({ user: data });
      return data;
    } catch {
      get().logout();
      return null;
    }
  },

  refreshAccessToken: async () => {
    const refreshToken = get().refreshToken;
    if (!refreshToken) return false;
    try {
      const { data } = await authApi.refresh(refreshToken);
      const persistent = data.persistent ?? get().persistent;
      set({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        persistent,
        expiresAt: data.expires_at ?? null,
      });
      saveTokens({
        accessToken: data.access_token,
        refreshToken: data.refresh_token,
        persistent,
        expiresAt: data.expires_at ?? null,
        user: get().user as unknown,
      });
      setAuthCookie(persistent);
      return true;
    } catch {
      return false;
    }
  },

  restoreSession: async () => {
    const saved = loadTokens();
    if (!saved) {
      set({ isInitialized: true });
      return false;
    }
    const expiresAt = saved.expiresAt;
    if (expiresAt) {
      try {
        const expiry = new Date(expiresAt).getTime();
        if (expiry <= Date.now()) {
          clearStoredTokens();
          set({ isInitialized: true });
          return false;
        }
      } catch {
        // Invalid date, try refresh anyway
      }
    }
    set({
      accessToken: saved.accessToken,
      refreshToken: saved.refreshToken,
      persistent: saved.persistent,
      expiresAt: saved.expiresAt ?? null,
      user: saved.user as User | null,
    });
    const success = await get().refreshAccessToken();
    if (!success) {
      clearStoredTokens();
      set({ isInitialized: true });
      return false;
    }
    const user = await get().fetchUser();
    if (user?.language) applyUserLanguage(user.language);
    set({ isInitialized: true });
    return true;
  },

  checkSessionExpiry: () => {
    const expiresAt = get().expiresAt;
    if (!expiresAt) return { valid: true };
    const expiry = new Date(expiresAt).getTime();
    const now = Date.now();
    const threeDays = 3 * 24 * 60 * 60 * 1000;
    if (expiry <= now) return { valid: false };
    if (expiry - now < threeDays && get().persistent) {
      return { valid: true, nearExpiry: true };
    }
    return { valid: true };
  },

  updateLanguage: async (code: string) => {
    applyUserLanguage(code);
    try {
      const { data } = await authApi.updateMe({ language: code });
      if (data) set({ user: data });
    } catch {
      // Local language change still applied
    }
  },

  init: async () => {
    const saved = loadTokens();
    if (!saved) {
      set({ isInitialized: true });
      return;
    }
    set({
      accessToken: saved.accessToken,
      refreshToken: saved.refreshToken,
      persistent: saved.persistent,
      expiresAt: saved.expiresAt ?? null,
    });
    const user = await get().fetchUser();
    if (user?.language) applyUserLanguage(user.language);
    set({ isInitialized: true });
  },
}));
