import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { AlertTriangle, CheckCircle2, Clock3, Copy, Gauge, Loader2, Play, Timer } from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { useAuthStore } from "@/stores/authStore";
import {
  useParsingActiveJob,
  useAdminStats,
  useParsingJobLiveFeed,
  useParsingMarketplacesDetailed,
  useParsingJobStatus,
  useParsingTestRuns,
  useParsingUsersDetailed,
  useRunParsingFullTest,
} from "@/hooks/useAdmin";

const RUNS_PAGE_SIZE = 20;
const RUNS_LIMIT = 500;

function formatDateTime(value: string | null, locale: string, fallback: string): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatDuration(seconds: number | null, fallback: string): string {
  if (seconds == null || Number.isNaN(seconds)) return fallback;
  const total = Math.max(0, Math.floor(seconds));
  const mm = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const ss = (total % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}

function statusBadgeVariant(status: "running" | "completed" | "failed") {
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  return "secondary";
}

function statusLabelKey(status: "running" | "completed" | "failed"): string {
  if (status === "completed") return "admin.marketplaces.status.success";
  if (status === "failed") return "admin.marketplaces.status.error";
  return "common.loading";
}

function stageToProgress(stage: string | null, status: "running" | "completed" | "failed"): number {
  if (status === "completed") return 100;
  if (status === "failed") return 100;
  if (!stage) return 5;
  if (stage === "queued") return 10;
  if (stage === "discovery") return 35;
  if (stage === "scrape") return 70;
  if (stage === "persist") return 90;
  return 15;
}

export function AdminPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [detailsJobId, setDetailsJobId] = useState<string | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const previousActiveStatus = useRef<"running" | "completed" | "failed" | null>(null);
  const previousAlertFingerprint = useRef<string>("");

  const { data: stats } = useAdminStats();
  const activeJobQuery = useParsingActiveJob(4500);
  const usersDetailedQuery = useParsingUsersDetailed(1000);
  const marketplacesDetailedQuery = useParsingMarketplacesDetailed(2000);
  const runsQuery = useParsingTestRuns(RUNS_LIMIT);
  const runPipeline = useRunParsingFullTest();

  const activeStatusQuery = useParsingJobStatus(activeJobId, {
    enabled: Boolean(activeJobId),
    refetchInterval: 4500,
  });
  const detailsStatusQuery = useParsingJobStatus(detailsJobId, {
    enabled: isDetailsOpen && Boolean(detailsJobId),
    refetchInterval: isDetailsOpen ? 4500 : false,
  });
  const liveFeedQuery = useParsingJobLiveFeed(liveJobId, {
    enabled: Boolean(liveJobId),
    refetchInterval: 3000,
    limit: 300,
    offset: 0,
  });

  useEffect(() => {
    const active = activeJobQuery.data?.active_job;
    if (!active || !active.job_id) return;
    setActiveJobId((prev) => prev ?? active.job_id);
    setLiveJobId((prev) => prev ?? active.job_id);
  }, [activeJobQuery.data]);

  const sortedRuns = useMemo(() => {
    const source = runsQuery.data ?? [];
    return [...source].sort((a, b) => {
      const aa = a.started_at ? new Date(a.started_at).getTime() : 0;
      const bb = b.started_at ? new Date(b.started_at).getTime() : 0;
      return bb - aa;
    });
  }, [runsQuery.data]);

  const totalPages = Math.max(1, Math.ceil(sortedRuns.length / RUNS_PAGE_SIZE));
  const pagedRuns = useMemo(() => {
    const safePage = Math.min(Math.max(historyPage, 1), totalPages);
    const start = (safePage - 1) * RUNS_PAGE_SIZE;
    return sortedRuns.slice(start, start + RUNS_PAGE_SIZE);
  }, [historyPage, sortedRuns, totalPages]);

  useEffect(() => {
    setHistoryPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  useEffect(() => {
    if (activeJobId) {
      setLiveJobId(activeJobId);
      return;
    }
    if (!liveJobId && sortedRuns[0]?.job_id) {
      setLiveJobId(sortedRuns[0].job_id);
    }
  }, [activeJobId, liveJobId, sortedRuns]);

  useEffect(() => {
    const status = activeStatusQuery.data?.status;
    if (!status) return;

    if (previousActiveStatus.current === "running" && (status === "completed" || status === "failed")) {
      const summary = activeStatusQuery.data?.metadata?.summary;
      if (status === "completed") {
        toast.success(
          `${t("admin.marketplaces.products")}: ${summary?.listings_created ?? 0}, ${t("common.price")}: ${summary?.prices_saved ?? 0}, ${t("admin.stats.errors")}: ${summary?.errors_count ?? 0}`,
        );
      } else {
        toast.error(t("admin.markets.refreshError"));
      }
      setActiveJobId(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-runs"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-marketplaces"] });
    }

    previousActiveStatus.current = status;
  }, [activeStatusQuery.data, queryClient, t]);

  const activeStatus = activeStatusQuery.data;
  const detailsStatus = detailsStatusQuery.data;
  const currentStage = activeStatus?.current_stage ?? "queued";
  const progress = stageToProgress(currentStage, activeStatus?.status ?? "running");
  const liveFeed = liveFeedQuery.data;
  const elapsedSeconds = useMemo(() => {
    if (!liveFeed?.started_at) return null;
    const start = new Date(liveFeed.started_at).getTime();
    if (Number.isNaN(start)) return null;
    const end = liveFeed.completed_at ? new Date(liveFeed.completed_at).getTime() : Date.now();
    if (Number.isNaN(end) || end < start) return null;
    return (end - start) / 1000;
  }, [liveFeed?.started_at, liveFeed?.completed_at]);
  const statusPieData = useMemo(
    () =>
      Object.entries(liveFeed?.status_counts ?? {}).map(([name, value]) => ({
        name,
        value,
      })),
    [liveFeed?.status_counts],
  );
  const stepsByMarketplace = useMemo(() => {
    const grouped = new Map<string, { success: number; failed: number }>();
    for (const step of liveFeed?.steps ?? []) {
      const key = step.marketplace_domain || step.marketplace_id.slice(0, 8);
      const existing = grouped.get(key) ?? { success: 0, failed: 0 };
      if (step.status === "success") {
        existing.success += 1;
      } else {
        existing.failed += 1;
      }
      grouped.set(key, existing);
    }
    return Array.from(grouped.entries()).map(([marketplace, values]) => ({
      marketplace,
      ...values,
    }));
  }, [liveFeed?.steps]);
  const throughputTimeline = useMemo(() => {
    const bucket = new Map<string, { minuteLabel: string; steps: number; success: number; failed: number }>();
    for (const step of liveFeed?.steps ?? []) {
      if (!step.created_at) continue;
      const ts = new Date(step.created_at);
      if (Number.isNaN(ts.getTime())) continue;
      const minuteKey = `${ts.getUTCFullYear()}-${String(ts.getUTCMonth() + 1).padStart(2, "0")}-${String(ts.getUTCDate()).padStart(2, "0")} ${String(ts.getUTCHours()).padStart(2, "0")}:${String(ts.getUTCMinutes()).padStart(2, "0")}`;
      const row = bucket.get(minuteKey) ?? {
        minuteLabel: `${String(ts.getHours()).padStart(2, "0")}:${String(ts.getMinutes()).padStart(2, "0")}`,
        steps: 0,
        success: 0,
        failed: 0,
      };
      row.steps += 1;
      if (step.status === "success") {
        row.success += 1;
      } else {
        row.failed += 1;
      }
      bucket.set(minuteKey, row);
    }
    return Array.from(bucket.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([, value]) => value);
  }, [liveFeed?.steps]);
  const ratePerMinute = useMemo(() => {
    if (!throughputTimeline.length) return 0;
    const total = throughputTimeline.reduce((sum, row) => sum + row.steps, 0);
    return total / throughputTimeline.length;
  }, [throughputTimeline]);
  const etaForecast = useMemo(() => {
    if (!liveFeed) return null;
    const estimatedTotal = liveFeed.estimated_total_steps ?? liveFeed.total_steps;
    const processed = liveFeed.total_steps;
    const remaining = Math.max(0, estimatedTotal - processed);
    if (remaining === 0 || processed === 0) {
      return {
        estimatedTotal,
        remaining,
        avgSeconds: 0,
        bestSeconds: 0,
        worstSeconds: 0,
      };
    }

    const averageRatePerMinute = Math.max(ratePerMinute, 0.1);
    const recentWindow = throughputTimeline.slice(-3);
    const recentRatePerMinute = recentWindow.length
      ? recentWindow.reduce((sum, row) => sum + row.steps, 0) / recentWindow.length
      : averageRatePerMinute;

    const bestRatePerMinute = Math.max(averageRatePerMinute * 1.25, recentRatePerMinute * 1.15, 0.2);
    const worstRatePerMinute = Math.max(Math.min(averageRatePerMinute * 0.65, recentRatePerMinute * 0.75), 0.05);

    const avgSeconds = (remaining * 60) / averageRatePerMinute;
    const bestSeconds = (remaining * 60) / bestRatePerMinute;
    const worstSeconds = (remaining * 60) / worstRatePerMinute;

    return {
      estimatedTotal,
      remaining,
      avgSeconds,
      bestSeconds,
      worstSeconds,
    };
  }, [liveFeed, ratePerMinute, throughputTimeline]);
  const qualityAlerts = useMemo(() => {
    if (!liveFeed || liveFeed.total_steps === 0) return [];
    const total = liveFeed.total_steps;
    const missingCritical = liveFeed.status_counts.missing_critical_data ?? 0;
    const technicalError = liveFeed.status_counts.technical_error ?? 0;
    const success = liveFeed.status_counts.success ?? 0;
    const missingCriticalRate = missingCritical / total;
    const technicalErrorRate = technicalError / total;
    const successRate = success / total;
    const rateLimitSteps = (liveFeed.steps ?? []).filter((step) =>
      (step.error_message ?? "").toLowerCase().includes("rate_limit")
      || (step.error_message ?? "").toLowerCase().includes("429")
    ).length;
    const rateLimitRate = rateLimitSteps / total;

    const alerts: Array<{ level: "warning" | "error"; code: string; message: string }> = [];
    if (missingCriticalRate >= 0.2) {
      alerts.push({
        level: "warning",
        code: "missing_critical_high",
        message: `High missing critical data: ${(missingCriticalRate * 100).toFixed(1)}%`,
      });
    }
    if (technicalErrorRate >= 0.1) {
      alerts.push({
        level: "error",
        code: "technical_error_high",
        message: `High technical errors: ${(technicalErrorRate * 100).toFixed(1)}%`,
      });
    }
    if (rateLimitRate >= 0.15) {
      alerts.push({
        level: "warning",
        code: "rate_limit_high",
        message: `High rate-limit pressure: ${(rateLimitRate * 100).toFixed(1)}%`,
      });
    }
    if (successRate < 0.55 && total >= 20) {
      alerts.push({
        level: "error",
        code: "success_rate_low",
        message: `Low success rate: ${(successRate * 100).toFixed(1)}%`,
      });
    }
    return alerts;
  }, [liveFeed]);

  useEffect(() => {
    if (!qualityAlerts.length) {
      previousAlertFingerprint.current = "";
      return;
    }
    const fingerprint = qualityAlerts.map((alert) => `${alert.code}:${alert.message}`).join("|");
    if (previousAlertFingerprint.current === fingerprint) return;
    previousAlertFingerprint.current = fingerprint;
    const critical = qualityAlerts.find((alert) => alert.level === "error");
    if (critical) {
      toast.error(critical.message);
      return;
    }
    toast.warning(qualityAlerts[0].message);
  }, [qualityAlerts]);

  if (!user?.is_superuser) {
    return (
      <div className="space-y-6">
        <PageHeader title="nav.admin" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title={t("common.error")}
              description={t("admin.markets.refreshError")}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="nav.admin" />

      <Tabs defaultValue="data-collection" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Market Overview</TabsTrigger>
          <TabsTrigger value="data-collection">Data Collection</TabsTrigger>
          <TabsTrigger value="users-management">Users Management</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("admin.title")}</CardTitle>
              <CardDescription>{t("admin.stats.scrapesToday")}</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.stats.users")}</p>
                <p className="text-2xl font-semibold">{stats?.users_count ?? stats?.users ?? 0}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.stats.marketplaces")}</p>
                <p className="text-2xl font-semibold">{stats?.marketplaces_count ?? stats?.marketplaces ?? 0}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.marketplaces.products")}</p>
                <p className="text-2xl font-semibold">{stats?.total_products_monitored ?? 0}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>{t("admin.pool.marketplaces")}</CardTitle>
                <CardDescription>{t("admin.marketplaces.successRate")}</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {marketplacesDetailedQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (marketplacesDetailedQuery.data?.length ?? 0) === 0 ? (
                <EmptyState title={t("common.noData")} description={t("admin.pool.marketplaces")} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("products.marketplace")}</TableHead>
                      <TableHead>{t("competitors.tableUrl")}</TableHead>
                      <TableHead>{t("admin.pool.productsInPool")}</TableHead>
                      <TableHead>Active listings</TableHead>
                      <TableHead>{t("admin.marketplaces.lastScrape")}</TableHead>
                      <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                      <TableHead>{t("admin.markets.lastRefresh")}</TableHead>
                      <TableHead>{t("common.status")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {marketplacesDetailedQuery.data?.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="max-w-60 truncate">{item.base_url}</TableCell>
                        <TableCell>{item.products_in_pool}</TableCell>
                        <TableCell>{item.active_listings}</TableCell>
                        <TableCell>{formatDateTime(item.last_scrape_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{item.success_rate.toFixed(2)}%</TableCell>
                        <TableCell>{formatDateTime(item.last_discovery_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>
                          <Badge variant={item.is_active ? "default" : "destructive"}>
                            {item.is_active ? "active" : "inactive"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="data-collection" className="space-y-6">
          <Card>
            <CardHeader className="space-y-3">
              <CardTitle>Data Collection</CardTitle>
              <CardDescription>
                Полный live-контроль сбора данных: стадии, ошибки, темп, прогноз и шаги в реальном времени.
              </CardDescription>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  className="w-full md:w-auto"
                  size="lg"
                  onClick={async () => {
                    try {
                      const result = await runPipeline.mutateAsync();
                      previousActiveStatus.current = "running";
                      setActiveJobId(result.job_id);
                      setLiveJobId(result.job_id);
                      toast.success(`${t("common.save")}: ${result.job_id}`);
                    } catch (error) {
                      const message =
                        typeof error === "object" &&
                        error &&
                        "response" in error &&
                        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                          : t("admin.markets.refreshError");
                      toast.error(message ?? t("admin.markets.refreshError"));
                    }
                  }}
                  disabled={runPipeline.isPending || activeStatus?.status === "running"}
                >
                  {runPipeline.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 size-4" />
                  )}
                  Run Data Collection
                </Button>
                {activeStatus && (
                  <Badge variant={statusBadgeVariant(activeStatus.status)}>
                    {t(statusLabelKey(activeStatus.status))}
                  </Badge>
                )}
                {activeStatus?.job_id && (
                  <span className="text-sm text-muted-foreground">{activeStatus.job_id}</span>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={progress} max={100} />
              <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
                <div className="rounded border p-3">{t("admin.pool.triggerDiscovery")}: {currentStage === "discovery" ? t("common.loading") : t("common.noData")}</div>
                <div className="rounded border p-3">{t("admin.pool.triggerScraping")}: {currentStage === "scrape" ? t("common.loading") : t("common.noData")}</div>
                <div className="rounded border p-3">{t("admin.pool.diagnostics")}: {currentStage === "persist" ? t("common.loading") : t("common.noData")}</div>
              </div>
              {liveFeed?.warning_flags?.length ? (
                <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
                  <div className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-300">
                    <AlertTriangle className="size-4" />
                    Обнаружены риски качества данных
                  </div>
                  {liveFeed.warning_flags.map((flag) => (
                    <span key={flag}>- {flag}</span>
                  ))}
                </div>
              ) : null}
              {qualityAlerts.length ? (
                <div className="flex flex-col gap-2 rounded border border-red-500/40 bg-red-500/5 p-3 text-sm">
                  <div className="flex items-center gap-2 font-medium text-red-700 dark:text-red-300">
                    <AlertTriangle className="size-4" />
                    Аномалии процесса сбора данных
                  </div>
                  {qualityAlerts.map((alert) => (
                    <div key={alert.code} className="flex items-center gap-2">
                      <Badge variant={alert.level === "error" ? "destructive" : "secondary"}>
                        {alert.level.toUpperCase()}
                      </Badge>
                      <span>{alert.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Elapsed</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Timer className="size-5 text-primary" />
                  {formatDuration(elapsedSeconds, t("common.dash"))}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Processed steps</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Gauge className="size-5 text-primary" />
                  {liveFeed?.total_steps ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Success rate</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <CheckCircle2 className="size-5 text-emerald-500" />
                  {liveFeed?.total_steps ? (((liveFeed.status_counts.success ?? 0) / liveFeed.total_steps) * 100).toFixed(1) : "0.0"}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">ETA (avg)</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Clock3 className="size-5 text-primary" />
                  {formatDuration(etaForecast?.avgSeconds ?? liveFeed?.estimated_remaining_seconds ?? null, t("common.dash"))}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Forecast window</CardTitle>
              <CardDescription>Прогноз завершения на основе фактической скорости обработки.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Best ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.bestSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Average ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.avgSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Worst ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.worstSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3 md:col-span-3">
                <p className="text-xs text-muted-foreground">Scope</p>
                <p className="text-sm">
                  processed {liveFeed?.total_steps ?? 0}
                  {etaForecast?.estimatedTotal ? ` / estimated ${etaForecast.estimatedTotal}` : ""}
                  {etaForecast?.remaining ? `, remaining ${etaForecast.remaining}` : ""}
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Status distribution</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {statusPieData.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Status distribution" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={statusPieData} dataKey="value" nameKey="name" outerRadius={100} label>
                        {statusPieData.map((entry, idx) => (
                          <Cell
                            key={`${entry.name}-${idx}`}
                            fill={entry.name === "success" ? "#16a34a" : entry.name === "missing_critical_data" ? "#f59e0b" : "#ef4444"}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Marketplace performance</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {stepsByMarketplace.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Marketplace performance" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stepsByMarketplace}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="marketplace" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="success" stackId="a" fill="#16a34a" />
                      <Bar dataKey="failed" stackId="a" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Throughput timeline</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {throughputTimeline.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Throughput timeline" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={throughputTimeline}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="minuteLabel" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <ReferenceLine y={ratePerMinute} stroke="#6366f1" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="steps" stroke="#0ea5e9" strokeWidth={2} dot={false} name="steps/min" />
                      <Line type="monotone" dataKey="success" stroke="#16a34a" strokeWidth={2} dot={false} name="success/min" />
                      <Line type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={2} dot={false} name="failed/min" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Live process log</CardTitle>
              <CardDescription>Каждая операция по листингу отображается в реальном времени.</CardDescription>
            </CardHeader>
            <CardContent>
              {liveFeedQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : !liveFeed ? (
                <EmptyState title={t("common.noData")} description="Live process log" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Marketplace</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>URL</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {liveFeed.steps.map((step) => (
                      <TableRow key={step.event_id}>
                        <TableCell>{formatDateTime(step.created_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{step.marketplace_domain || step.marketplace_id.slice(0, 8)}</TableCell>
                        <TableCell>
                          <Badge variant={step.status === "success" ? "default" : "secondary"}>{step.status}</Badge>
                        </TableCell>
                        <TableCell>{step.duration_ms ?? t("common.dash")}</TableCell>
                        <TableCell>{step.price_found ?? t("common.dash")}</TableCell>
                        <TableCell className="max-w-72 truncate">{step.url}</TableCell>
                        <TableCell className="max-w-80 truncate">{step.error_message || t("common.dash")}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("admin.pool.discoveryLogs")}</CardTitle>
              <CardDescription>{t("admin.pool.diagnosticsResult")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {runsQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : sortedRuns.length === 0 ? (
                <EmptyState title={t("common.noData")} description={t("admin.pool.discoveryLogs")} />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("admin.pool.diagnostics")}</TableHead>
                        <TableHead>{t("alerts.date")}</TableHead>
                        <TableHead>{t("admin.markets.lastRefresh")}</TableHead>
                        <TableHead>{t("admin.claude.avgLatency")}</TableHead>
                        <TableHead>{t("admin.marketplaces.products")}</TableHead>
                        <TableHead>{t("common.price")}</TableHead>
                        <TableHead>{t("admin.stats.errors")}</TableHead>
                        <TableHead>{t("common.status")}</TableHead>
                        <TableHead>Live</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pagedRuns.map((run) => (
                        <TableRow
                          key={run.job_id}
                          className="cursor-pointer"
                          onClick={() => {
                            setDetailsJobId(run.job_id);
                            setIsDetailsOpen(true);
                          }}
                        >
                          <TableCell>
                            <button
                              type="button"
                              className="inline-flex items-center gap-2 text-left text-sm text-primary hover:underline"
                              onClick={(event) => {
                                event.stopPropagation();
                                navigator.clipboard.writeText(run.job_id);
                                toast.success(t("common.copied"));
                              }}
                            >
                              <Copy className="size-3.5" />
                              {run.job_id.slice(0, 8)}…
                            </button>
                          </TableCell>
                          <TableCell>{formatDateTime(run.started_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                          <TableCell>{formatDateTime(run.completed_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                          <TableCell>{formatDuration(run.duration_seconds, t("common.dash"))}</TableCell>
                          <TableCell>{run.listings_created}</TableCell>
                          <TableCell>{run.prices_saved}</TableCell>
                          <TableCell>{run.errors_count}</TableCell>
                          <TableCell>
                            <Badge variant={statusBadgeVariant(run.status)}>
                              {t(statusLabelKey(run.status))}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                setLiveJobId(run.job_id);
                                toast.success(`Live feed: ${run.job_id.slice(0, 8)}…`);
                              }}
                            >
                              Watch
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">{historyPage}/{totalPages}</p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                        disabled={historyPage <= 1}
                      >
                        {t("common.back")}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={historyPage >= totalPages}
                      >
                        {t("common.next")}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users-management">
          <Card>
            <CardHeader>
              <CardTitle>Users Management</CardTitle>
              <CardDescription>Полная таблица пользователей с активностью и нагрузкой.</CardDescription>
            </CardHeader>
            <CardContent>
              {usersDetailedQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : (usersDetailedQuery.data?.length ?? 0) === 0 ? (
                <EmptyState title={t("common.noData")} description="Users Management" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Email</TableHead>
                      <TableHead>Name</TableHead>
                      <TableHead>Plan</TableHead>
                      <TableHead>Tracked</TableHead>
                      <TableHead>Login count</TableHead>
                      <TableHead>Last login</TableHead>
                      <TableHead>Created</TableHead>
                      <TableHead>Status</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {usersDetailedQuery.data?.map((userRow) => (
                      <TableRow key={userRow.id}>
                        <TableCell>{userRow.email}</TableCell>
                        <TableCell>{userRow.name || t("common.dash")}</TableCell>
                        <TableCell>{userRow.plan}</TableCell>
                        <TableCell>{userRow.tracked_products}</TableCell>
                        <TableCell>{userRow.login_count}</TableCell>
                        <TableCell>{formatDateTime(userRow.last_login_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{formatDateTime(userRow.created_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>
                          <Badge variant={userRow.is_active ? "default" : "destructive"}>
                            {userRow.is_active ? "active" : "inactive"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

      <Dialog
        open={isDetailsOpen}
        onOpenChange={(open) => {
          setIsDetailsOpen(open);
          if (!open) setDetailsJobId(null);
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              {t("admin.pool.diagnosticsResult")}{" "}
              {detailsStatus?.job_id ? `#${detailsStatus.job_id.slice(0, 8)}` : ""}
            </DialogTitle>
            <DialogDescription>{t("admin.pool.diagnostics")}</DialogDescription>
          </DialogHeader>

          {detailsStatusQuery.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : detailsStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("common.status")}</p>
                    <Badge variant={statusBadgeVariant(detailsStatus.status)}>
                      {t(statusLabelKey(detailsStatus.status))}
                    </Badge>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("alerts.date")}</p>
                    <p className="text-sm">
                      {formatDateTime(detailsStatus.started_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("admin.markets.lastRefresh")}</p>
                    <p className="text-sm">
                      {formatDateTime(detailsStatus.completed_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("admin.claude.avgLatency")}</p>
                    <p className="text-sm">{formatDuration(detailsStatus.duration_seconds, t("common.dash"))}</p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("admin.pool.diagnosticsResult")}</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-2 text-sm md:grid-cols-4">
                  <div className="rounded border p-2">
                    {t("admin.pool.triggerDiscovery")}: {detailsStatus.metadata?.timings?.discovery_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.pool.triggerScraping")}: {detailsStatus.metadata?.timings?.scrape_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.pool.diagnostics")}: {detailsStatus.metadata?.timings?.persist_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.claude.tokens24h")}: {detailsStatus.metadata?.timings?.total_ms ?? 0} ms
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("admin.pool.marketplaces")}</CardTitle>
                </CardHeader>
                <CardContent>
                  {(detailsStatus.metadata?.per_marketplace?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">{t("common.noData")}</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t("products.marketplace")}</TableHead>
                          <TableHead>{t("admin.marketplaces.products")}</TableHead>
                          <TableHead>{t("common.price")}</TableHead>
                          <TableHead>{t("admin.stats.errors")}</TableHead>
                          <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                          <TableHead>{t("common.status")}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailsStatus.metadata?.per_marketplace?.map((row) => {
                          const denominator = row.prices_saved + row.errors_count;
                          const rate = denominator > 0 ? (row.prices_saved / denominator) * 100 : 0;
                          return (
                            <TableRow key={`${row.marketplace_id}-${row.domain}`}>
                              <TableCell>{row.domain}</TableCell>
                              <TableCell>{row.listings_created}</TableCell>
                              <TableCell>{row.prices_saved}</TableCell>
                              <TableCell>{row.errors_count}</TableCell>
                              <TableCell>{rate.toFixed(2)}%</TableCell>
                              <TableCell>
                                <Badge variant={statusBadgeVariant(row.status)}>
                                  {t(statusLabelKey(row.status))}
                                </Badge>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <EmptyState
              title={t("common.error")}
              description={t("admin.markets.refreshError")}
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              {t("common.close")}
            </Button>
            <Button
              onClick={async () => {
                try {
                  const result = await runPipeline.mutateAsync();
                  previousActiveStatus.current = "running";
                  setActiveJobId(result.job_id);
                  setLiveJobId(result.job_id);
                  setIsDetailsOpen(false);
                  toast.success(`${t("common.refresh")}: ${result.job_id}`);
                } catch {
                  toast.error(t("admin.markets.refreshError"));
                }
              }}
              disabled={runPipeline.isPending}
            >
              {runPipeline.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Clock3 className="mr-2 size-4" />
              )}
              {t("common.refresh")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
