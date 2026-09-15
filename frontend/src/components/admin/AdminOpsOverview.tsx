/**
 * Operator ops overview — the admin landing tab.
 * One screen answers: is the pipeline running, is anything on fire,
 * how big is the pool. Everything links into the deeper admin sections.
 */

import { useMemo } from "react";
import { Link } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { Activity, ArrowRight, Bell, Database, Store, Users } from "lucide-react";
import * as adminApi from "@/api/admin";
import { useServiceAlerts } from "@/hooks/useAdmin";
import { formatRelativeTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";

function SeverityChip({
  severity,
  count,
}: {
  severity: "critical" | "error" | "warning" | "info";
  count: number;
}) {
  const { t } = useTranslation();
  const tone =
    severity === "critical" || severity === "error"
      ? "border-[var(--status-error-border)] bg-[var(--status-error-bg)] text-[var(--status-error)]"
      : severity === "warning"
        ? "border-[var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn)]"
        : "border-[var(--accent-border)] bg-[var(--accent-bg)] text-[var(--accent)]";
  const labels: Record<typeof severity, string> = {
    critical: t("admin.alerts.severity.critical"),
    error: t("admin.alerts.severity.error"),
    warning: t("admin.alerts.severity.warning"),
    info: t("admin.alerts.severity.info"),
  };
  return (
    <span
      className={cn(
        "label-mono inline-flex items-center gap-1.5 rounded-full border px-2.5 py-1",
        count === 0 ? "border-[var(--glass-border)] bg-transparent !text-[var(--foreground-subtle)]" : tone,
      )}
    >
      {labels[severity]}
      <span className="tabular-nums">{count}</span>
    </span>
  );
}

function OpsCard({
  title,
  to,
  children,
}: {
  title: string;
  to?: string;
  children: React.ReactNode;
}) {
  const { t } = useTranslation();
  return (
    <div className="surface-base flex min-w-0 flex-col rounded-xl p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="label-mono !text-[var(--foreground)]">{title}</h3>
        {to ? (
          <Link
            to={to}
            className="inline-flex items-center gap-1 text-xs text-[var(--accent)] hover:underline"
          >
            {t("admin.ops.open")}
            <ArrowRight className="size-3" />
          </Link>
        ) : null}
      </div>
      {children}
    </div>
  );
}

export function AdminOpsOverview() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  const { data: activeJob } = useQuery({
    queryKey: ["admin", "parsing", "active-job", "ops"],
    queryFn: () => adminApi.getParsingActiveJob().then((r) => r.data),
    refetchInterval: 15_000,
  });

  const { data: stats } = useQuery({
    queryKey: ["admin", "stats", "ops"],
    queryFn: () => adminApi.getAdminStats().then((r) => r.data),
    refetchInterval: 60_000,
  });

  const { data: openAlerts } = useServiceAlerts({ resolved: "open", limit: 200 });

  const severityCounts = useMemo(() => {
    const counts = { critical: 0, error: 0, warning: 0, info: 0 };
    for (const alert of openAlerts?.items ?? []) {
      if (alert.severity in counts) {
        counts[alert.severity as keyof typeof counts] += 1;
      }
    }
    return counts;
  }, [openAlerts?.items]);

  const job = activeJob?.active_job ?? null;
  const scrapesTotal = stats?.total_scrapes_today ?? 0;
  const scrapesFailed = stats?.failed_scrapes_today ?? 0;

  return (
    <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
      <OpsCard title={t("admin.ops.pipeline")} to="/admin/data-collection">
        {job ? (
          <div className="space-y-2">
            <div className="flex items-center gap-2">
              <span className="relative flex size-2.5">
                <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-[var(--status-ok)] opacity-60" />
                <span className="relative inline-flex size-2.5 rounded-full bg-[var(--status-ok)]" />
              </span>
              <span className="text-sm font-medium">
                {t("admin.ops.runActive")}
              </span>
            </div>
            <p className="font-mono text-xs text-muted-foreground">
              {job.job_id.slice(0, 8)}… · {job.current_stage ?? job.status}
              {job.started_at
                ? ` · ${formatRelativeTime(job.started_at, locale)}`
                : null}
            </p>
          </div>
        ) : (
          <p className="text-sm text-muted-foreground">{t("admin.ops.runIdle")}</p>
        )}
        <div className="mt-3 flex items-center gap-4 border-t border-[var(--glass-border)] pt-3">
          <div>
            <p className="label-mono">{t("admin.stats.scrapesToday")}</p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">{scrapesTotal}</p>
          </div>
          <div>
            <p className="label-mono">{t("admin.stats.errors")}</p>
            <p
              className={cn(
                "mt-0.5 text-lg font-semibold tabular-nums",
                scrapesFailed > 0 && "text-[var(--status-error)]",
              )}
            >
              {scrapesFailed}
            </p>
          </div>
        </div>
      </OpsCard>

      <OpsCard title={t("admin.ops.alerts")} to="/admin/alerts">
        <p className="text-2xl font-semibold tabular-nums">
          {openAlerts?.total ?? 0}
          <span className="ms-2 align-middle text-xs font-normal text-muted-foreground">
            {t("admin.ops.openCount")}
          </span>
        </p>
        <div className="mt-3 flex flex-wrap gap-1.5">
          <SeverityChip severity="critical" count={severityCounts.critical} />
          <SeverityChip severity="error" count={severityCounts.error} />
          <SeverityChip severity="warning" count={severityCounts.warning} />
          <SeverityChip severity="info" count={severityCounts.info} />
        </div>
      </OpsCard>

      <OpsCard title={t("admin.ops.inventory")} to="/admin/overview">
        <div className="grid grid-cols-3 gap-3">
          <div>
            <p className="label-mono flex items-center gap-1">
              <Database className="size-3" aria-hidden />
              {t("market.overview.kpi.totalPool")}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">
              {stats?.products_in_pool ?? 0}
            </p>
          </div>
          <div>
            <p className="label-mono flex items-center gap-1">
              <Store className="size-3" aria-hidden />
              {t("admin.stats.marketplaces")}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">
              {stats?.marketplaces_count ?? stats?.marketplaces ?? 0}
            </p>
          </div>
          <div>
            <p className="label-mono flex items-center gap-1">
              <Users className="size-3" aria-hidden />
              {t("admin.stats.users")}
            </p>
            <p className="mt-0.5 text-lg font-semibold tabular-nums">
              {stats?.users_count ?? stats?.users ?? 0}
            </p>
          </div>
        </div>
        <div className="mt-3 flex items-center gap-2 border-t border-[var(--glass-border)] pt-3 text-xs text-muted-foreground">
          <Activity className="size-3.5 shrink-0" aria-hidden />
          {t("admin.ops.inventoryHint")}
        </div>
      </OpsCard>

      <div className="lg:col-span-2 xl:col-span-3">
        <OpsCard title={t("admin.ops.latestAlerts")} to="/admin/alerts">
          {(openAlerts?.items?.length ?? 0) === 0 ? (
            <p className="flex items-center gap-2 text-sm text-muted-foreground">
              <Bell className="size-4" aria-hidden />
              {t("admin.ops.allClear")}
            </p>
          ) : (
            <ul className="divide-y divide-[var(--glass-border)]">
              {(openAlerts?.items ?? []).slice(0, 5).map((alert) => (
                <li key={alert.id} className="flex items-center gap-3 py-2">
                  <span
                    className={cn(
                      "h-6 w-0.5 shrink-0 rounded-full",
                      alert.severity === "critical" || alert.severity === "error"
                        ? "bg-[var(--status-error)]"
                        : alert.severity === "warning"
                          ? "bg-[var(--status-warn)]"
                          : "bg-[var(--accent)]",
                    )}
                    aria-hidden
                  />
                  <span className="label-mono shrink-0">
                    {alert.module} → {alert.submodule}
                  </span>
                  <span className="min-w-0 flex-1 truncate text-sm text-muted-foreground">
                    {alert.message}
                  </span>
                  <span className="shrink-0 text-xs text-muted-foreground">
                    {formatRelativeTime(alert.triggered_at, locale)}
                  </span>
                </li>
              ))}
            </ul>
          )}
        </OpsCard>
      </div>
    </div>
  );
}
