/**
 * Client alerts stream — latest alert events on the Overview dashboard.
 * Backed by GET /api/alerts/events (P3). The trigger engine ships in the
 * next backend slice, so an empty feed is the honest current state.
 */

import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { ArrowRight, Bell } from "lucide-react";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { useAlertEvents } from "@/hooks/useAlerts";
import { formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

export function AlertsStreamWidget() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { data, isError } = useAlertEvents({ limit: 5, offset: 0 });
  const events = data?.items ?? [];

  return (
    <div className="surface-base flex h-full min-w-0 flex-col rounded-xl p-3.5">
      <div className="mb-3 flex items-start justify-between gap-2">
        <div>
          <h3 className="label-mono !text-[var(--foreground)]">{t("dashboard.alerts.title")}</h3>
          <p className="mt-1 text-2xs text-muted-foreground">{t("dashboard.alerts.subtitle")}</p>
        </div>
        <Link
          to="/alerts"
          className="inline-flex shrink-0 items-center gap-1 text-xs text-[var(--accent)] hover:underline"
        >
          {t("admin.ops.open")}
          <ArrowRight className="size-3" />
        </Link>
      </div>
      {isError ? (
        <p className="text-sm text-muted-foreground">{t("common.error")}</p>
      ) : events.length === 0 ? (
        <EmptyState
          title="dashboard.alerts.empty"
          description="dashboard.alerts.emptyHint"
          icon={Bell}
          className="py-6"
        />
      ) : (
        <ul className="min-h-0 flex-1 divide-y divide-[var(--glass-border)] overflow-y-auto">
          {events.map((event) => {
            const change = event.change_pct == null ? null : safeNumber(event.change_pct);
            return (
              <li key={event.id} className="flex items-center gap-2 py-2">
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
    </div>
  );
}
