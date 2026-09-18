/**
 * Header bell — the in_app alert channel's surface (P15).
 * Badge counts alert events newer than the last time the bell was opened;
 * the dropdown lists the latest events and links to the Alerts page.
 */

import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, Bell } from "lucide-react";
import { useAlertEvents } from "@/hooks/useAlerts";
import { useNotificationsStore } from "@/stores/notificationsStore";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

export function NotificationsMenu() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const lastSeenAt = useNotificationsStore((state) => state.lastSeenAt);
  const markSeen = useNotificationsStore((state) => state.markSeen);

  const { data } = useAlertEvents({ limit: 8, offset: 0 });
  const events = useMemo(() => data?.items ?? [], [data?.items]);

  const unreadCount = useMemo(() => {
    if (lastSeenAt == null) {
      return events.length;
    }
    const seen = Date.parse(lastSeenAt);
    return events.filter((event) => Date.parse(event.triggered_at) > seen).length;
  }, [events, lastSeenAt]);

  return (
    <DropdownMenu
      onOpenChange={(open) => {
        if (open) {
          markSeen();
        }
      }}
    >
      <DropdownMenuTrigger asChild>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "relative min-h-9 min-w-9 size-9 touch-manipulation transition-colors",
            "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]"
          )}
          aria-label={t("common.notifications")}
        >
          <Bell className="size-4 text-[var(--foreground)]" />
          {unreadCount > 0 && (
            <span
              className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-2xs font-bold"
              style={{
                background: "var(--accent)",
                color: "var(--primary-foreground)",
              }}
            >
              {unreadCount > 99 ? "99+" : unreadCount}
            </span>
          )}
        </Button>
      </DropdownMenuTrigger>
      <DropdownMenuContent align="end" className="w-80 surface-overlay p-0">
        <div className="px-3 py-2">
          <p className="label-mono">{t("common.notifications")}</p>
        </div>
        <DropdownMenuSeparator className="my-0 bg-[var(--glass-border)]" />
        {events.length === 0 ? (
          <p className="px-3 py-4 text-sm text-muted-foreground">
            {t("dashboard.alerts.empty")}
          </p>
        ) : (
          <ul className="max-h-72 overflow-y-auto">
            {events.map((event) => {
              const change = event.change_pct == null ? null : safeNumber(event.change_pct);
              return (
                <li
                  key={event.id}
                  className="flex items-center gap-2 border-b border-[var(--glass-border)] px-3 py-2 last:border-b-0"
                >
                  <div className="min-w-0 flex-1">
                    <p className="truncate text-sm">{event.product_title ?? "—"}</p>
                    <p className="truncate text-xs text-muted-foreground">
                      {event.marketplace_name ?? "—"} ·{" "}
                      {formatRelativeTime(event.triggered_at, locale)}
                    </p>
                  </div>
                  {change != null ? (
                    <span
                      className={cn(
                        "shrink-0 font-mono text-xs font-medium tabular-nums",
                        change > 0
                          ? "text-[var(--color-price-up)]"
                          : "text-[var(--color-price-down)]",
                      )}
                    >
                      {change > 0 ? "+" : ""}
                      {change.toFixed(2)}%
                    </span>
                  ) : null}
                </li>
              );
            })}
          </ul>
        )}
        <DropdownMenuSeparator className="my-0 bg-[var(--glass-border)]" />
        <Link
          to="/alerts"
          className="flex items-center justify-center gap-1 px-3 py-2 text-xs text-[var(--accent)] hover:underline"
        >
          {t("notifications.viewAll")}
          <ArrowRight className="size-3" />
        </Link>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
