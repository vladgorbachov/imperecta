import { create } from "zustand";
import i18n from "i18next";
import {
  clearStoredTokens,
  getStoredToken,
  setStoredToken,
} from "@/api/client";
import { authApi } from "@/api/auth";

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
}

interface AuthState {
  user: User | null;
  accessToken: string | null;
  refreshToken: string | null;
  isInitialized: boolean;
  login: (email: string, password: string) => Promise<void>;
  register: (email: string, password: string, name: string, companyName?: string, language?: string) => Promise<void>;
  logout: () => void;
  setUser: (user: User | null) => void;
  fetchUser: () => Promise<User | null>;
  updateLanguage: (code: string) => Promise<void>;
  init: () => Promise<void>;
}

export const useAuthStore = create<AuthState>((set, get) => ({
  user: null,
  accessToken: getStoredToken(),
  refreshToken: null,
  isInitialized: false,

  login: async (email: string, password: string) => {
    const { data } = await authApi.login(email, password);
    setStoredToken(data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    });
    await get().fetchUser();
  },

  register: async (
    email: string,
    password: string,
    name: string,
    companyName?: string,
    language?: string
  ) => {
    const { data } = await authApi.register(email, password, name, companyName, language);
    setStoredToken(data.access_token);
    localStorage.setItem("refresh_token", data.refresh_token);
    set({
      accessToken: data.access_token,
      refreshToken: data.refresh_token,
    });
    await get().fetchUser();
  },

  logout: () => {
    clearStoredTokens();
    set({ user: null, accessToken: null, refreshToken: null });
  },

  setUser: (user) => set({ user }),

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

  updateLanguage: async (code: string) => {
    applyUserLanguage(code);
    try {
      const { data } = await authApi.updateMe({ language: code });
      if (data) set({ user: data });
    } catch {
      // Local language change still applied; API error ignored
    }
  },

  init: async () => {
    const token = getStoredToken();
    if (!token) {
      set({ isInitialized: true });
      return;
    }
    set({ accessToken: token });
    const user = await get().fetchUser();
    if (user?.language) {
      applyUserLanguage(user.language);
    }
    set({ isInitialized: true });
  },
}));
