/**
 * Client alerts stream — latest alert events on the Overview dashboard.
 * Backed by GET /api/alerts/events (P3). The trigger engine ships in the
 * next backend slice, so an empty feed is the honest current state.
 *
 * Below the feed: 24h price-change distribution — a histogram over the same
 * movements the Pulse/Movers widgets read, plus median and drop/rise shares.
 * Fills the widget with analyst-grade signal while the alert feed is short.
 */

import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ArrowRight, Bell } from "lucide-react";
import {
  marketsApi,
  marketsQueryKeys,
  type MovementsQueryParams,
} from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { useAlertEvents } from "@/hooks/useAlerts";
import { formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

/** Bucket edges for the Δ24h histogram (open-ended tails). */
const BUCKET_EDGES = [-20, -10, -5, 0, 5, 10, 20];
const BUCKET_COUNT = BUCKET_EDGES.length + 1;
const DISTRIBUTION_SAMPLE = 200;

interface DistributionStats {
  buckets: number[];
  maxBucket: number;
  median: number;
  drops: number;
  rises: number;
  n: number;
}

function ChangeDistribution({ countryCode }: { countryCode: string | null }) {
  const { t } = useTranslation();

  const params = useMemo(
    (): MovementsQueryParams => ({
      period: "24h",
      direction: "all",
      sort_by: "changed_at",
      limit: DISTRIBUTION_SAMPLE,
      offset: 0,
      country_code: countryCode ?? undefined,
    }),
    [countryCode],
  );
  const { data } = useQuery({
    queryKey: marketsQueryKeys.movements(params),
    queryFn: () => marketsApi.getMovers(params).then((r) => r.data),
    staleTime: 60_000,
    refetchInterval: 120_000,
  });

  const stats = useMemo((): DistributionStats | null => {
    const values = (data?.items ?? [])
      .map((item) => safeNumber(item.price_change_pct))
      .filter((value) => Number.isFinite(value));
    if (values.length === 0) {
      return null;
    }
    const sorted = [...values].sort((a, b) => a - b);
    const mid = Math.floor(sorted.length / 2);
    const median =
      sorted.length % 2 === 1 ? sorted[mid] : (sorted[mid - 1] + sorted[mid]) / 2;
    const buckets = new Array<number>(BUCKET_COUNT).fill(0);
    for (const value of values) {
      const edgeIndex = BUCKET_EDGES.findIndex((edge) => value < edge);
      buckets[edgeIndex === -1 ? BUCKET_COUNT - 1 : edgeIndex] += 1;
    }
    return {
      buckets,
      maxBucket: Math.max(...buckets),
      median,
      drops: values.filter((value) => value < 0).length,
      rises: values.filter((value) => value > 0).length,
      n: values.length,
    };
  }, [data]);

  return (
    <div className="mt-auto pt-4" data-testid="change-distribution">
      <div className="border-t border-[var(--glass-border)] pt-3">
        <p className="label-mono mb-2">{t("dashboard.distribution.title")}</p>
        {stats == null ? (
          <p className="py-2 text-sm text-muted-foreground">
            {t("dashboard.distribution.empty")}
          </p>
        ) : (
          <>
            <div className="flex h-20 items-end gap-1" aria-hidden>
              {stats.buckets.map((count, index) => {
                /* Buckets left of the 0-edge are price drops (green per the
                   price-semantics canon), the rest are rises (red). */
                const isDropSide = index < 4;
                const height =
                  count === 0
                    ? 0
                    : Math.max(6, Math.round((count / stats.maxBucket) * 100));
                return (
                  <div
                    key={index}
                    className="flex h-full flex-1 flex-col justify-end"
                    title={`${count}`}
                  >
                    <div
                      className={cn(
                        "rounded-sm transition-[height] duration-500",
                        count === 0 && "h-px bg-[var(--glass-border)]",
                      )}
                      style={
                        count === 0
                          ? undefined
                          : {
                              height: `${height}%`,
                              background: isDropSide
                                ? "var(--color-price-down)"
                                : "var(--color-price-up)",
                              opacity: 0.85,
                            }
                      }
                    />
                  </div>
                );
              })}
            </div>
            <div className="mt-1 flex justify-between font-mono text-2xs text-muted-foreground">
              <span>≤-20%</span>
              <span>0</span>
              <span>≥+20%</span>
            </div>
            <div className="mt-3 grid grid-cols-3 gap-2">
              <div>
                <p className="label-mono">{t("dashboard.distribution.median")}</p>
                <p
                  className={cn(
                    "font-mono text-sm font-medium tabular-nums",
                    stats.median > 0
                      ? "text-[var(--color-price-up)]"
                      : stats.median < 0
                        ? "text-[var(--color-price-down)]"
                        : undefined,
                  )}
                >
                  {stats.median > 0 ? "+" : ""}
                  {stats.median.toFixed(1)}%
                </p>
              </div>
              <div>
                <p className="label-mono">{t("dashboard.distribution.drops")}</p>
                <p className="font-mono text-sm tabular-nums text-[var(--color-price-down)]">
                  {stats.drops}
                  <span className="text-muted-foreground">
                    {" "}
                    · {Math.round((stats.drops / stats.n) * 100)}%
                  </span>
                </p>
              </div>
              <div>
                <p className="label-mono">{t("dashboard.distribution.rises")}</p>
                <p className="font-mono text-sm tabular-nums text-[var(--color-price-up)]">
                  {stats.rises}
                  <span className="text-muted-foreground">
                    {" "}
                    · {Math.round((stats.rises / stats.n) * 100)}%
                  </span>
                </p>
              </div>
            </div>
            <p className="mt-2 text-2xs text-muted-foreground">
              {t("dashboard.distribution.sample", { count: stats.n })}
            </p>
          </>
        )}
      </div>
    </div>
  );
}

export function AlertsStreamWidget({
  countryCode = null,
}: {
  countryCode?: string | null;
}) {
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
          className="py-4"
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
      <ChangeDistribution countryCode={countryCode} />
    </div>
  );
}
