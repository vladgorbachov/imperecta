/**
 * Session expiry warning: shows dialog when session is expiring soon or expired.
 * For persistent sessions only. Checks every 60 seconds.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { useAuthStore } from "@/stores/authStore";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "@/components/ui/dialog";
import { Button } from "@/components/ui/button";

const DISMISSED_KEY = "imperecta_expiry_dismissed";
const DISMISS_DURATION_MS = 24 * 60 * 60 * 1000; // 24 hours
const CHECK_INTERVAL_MS = 60 * 1000; // 60 seconds
const THREE_DAYS_MS = 3 * 24 * 60 * 60 * 1000;

export function SessionExpiryWarning() {
  const { t } = useTranslation();
  const { accessToken, persistent, expiresAt, refreshAccessToken, logout } =
    useAuthStore();

  const [expiredOpen, setExpiredOpen] = useState(false);
  const [expiringOpen, setExpiringOpen] = useState(false);
  const [daysLeft, setDaysLeft] = useState<number>(0);

  useEffect(() => {
    if (!accessToken || !persistent) return;

    const check = () => {
      const currentExpiresAt = useAuthStore.getState().expiresAt;
      if (!currentExpiresAt) return;
      const expiry = new Date(currentExpiresAt).getTime();
      const now = Date.now();

      if (expiry <= now) {
        setExpiredOpen(true);
        setExpiringOpen(false);
        return;
      }

      const dismissed = localStorage.getItem(DISMISSED_KEY);
      if (dismissed) {
        const dismissedAt = parseInt(dismissed, 10);
        if (now - dismissedAt < DISMISS_DURATION_MS) return;
      }

      const remaining = expiry - now;
      if (remaining < THREE_DAYS_MS) {
        setDaysLeft(Math.ceil(remaining / (24 * 60 * 60 * 1000)));
        setExpiringOpen(true);
      }
    };

    check();
    const id = setInterval(check, CHECK_INTERVAL_MS);
    return () => clearInterval(id);
  }, [accessToken, persistent]);

  const handleExtend = async () => {
    const success = await refreshAccessToken();
    if (success) {
      setExpiringOpen(false);
    }
  };

  const handleLater = () => {
    localStorage.setItem(DISMISSED_KEY, Date.now().toString());
    setExpiringOpen(false);
  };

  const handleExpiredLogin = () => {
    setExpiredOpen(false);
    logout();
  };

  return (
    <>
      <Dialog open={expiredOpen} onOpenChange={() => {}}>
        <DialogContent
          onPointerDownOutside={(e) => e.preventDefault()}
          onEscapeKeyDown={(e) => e.preventDefault()}
        >
          <DialogHeader>
            <DialogTitle>{t("session.expired.title")}</DialogTitle>
            <DialogDescription>{t("session.expired.message")}</DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button onClick={handleExpiredLogin}>{t("session.expired.login")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={expiringOpen} onOpenChange={setExpiringOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("session.expiringSoon.title")}</DialogTitle>
            <DialogDescription>
              {t("session.expiringSoon.message", { days: daysLeft })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={handleLater}>
              {t("session.expiringSoon.later")}
            </Button>
            <Button onClick={handleExtend}>{t("session.expiringSoon.extend")}</Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </>
  );
}
