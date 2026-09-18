/**
 * In-app notifications state: when the user last opened the bell.
 * Alert events newer than this timestamp count as unread on the badge.
 * Persisted per browser — matches the in_app alert channel (P15).
 */

import { create } from "zustand";
import { persist } from "zustand/middleware";

interface NotificationsState {
  /** ISO timestamp of the last time the bell dropdown was opened. */
  lastSeenAt: string | null;
  markSeen: () => void;
}

export const useNotificationsStore = create<NotificationsState>()(
  persist(
    (set) => ({
      lastSeenAt: null,
      markSeen: () => set({ lastSeenAt: new Date().toISOString() }),
    }),
    { name: "imperecta_notifications" },
  ),
);
