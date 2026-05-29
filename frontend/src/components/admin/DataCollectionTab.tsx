import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import type { ReactNode } from "react";
import {
  AlertTriangle,
  Copy,
  Gauge,
  Loader2,
  Play,
  Square,
  Timer,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Checkbox } from "@/components/ui/checkbox";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ParsingJobStatus, ParsingPipelineRun } from "@/api/admin";
import {
  useCancelParsingActiveJob,
  useParsingActiveJob,
  useParsingJobLiveFeed,
  useParsingJobStatus,
  useParsingMarketplacesDetailed,
  useParsingPipelineRuns,
  useRunParsingPipeline,
} from "@/hooks/useAdmin";

const RUNS_PAGE_SIZE = 20;
const RUNS_LIMIT = 200;
const STALE_ACTIVITY_SECONDS = 300;

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
  const hh = Math.floor(total / 3600);
  const mm = Math.floor((total % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const ss = (total % 60).toString().padStart(2, "0");
  if (hh > 0) {
    return `${hh}:${mm}:${ss}`;
  }
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

function stageLabelKey(stage: string | null | undefined): string {
  switch (stage) {
    case "dispatching":
      return "admin.dataCollection.stage.dispatching";
    case "discovery":
      return "admin.dataCollection.stage.discovery";
    case "scrape":
      return "admin.dataCollection.stage.scrape";
    case "persist":
      return "admin.dataCollection.stage.persist";
    case "completed":
      return "admin.dataCollection.stage.completed";
    case "failed":
      return "admin.dataCollection.stage.failed";
    case "queued":
      return "admin.dataCollection.stage.queued";
    default:
      return "admin.dataCollection.stage.unknown";
  }
}

function computeProgress(
  status: ParsingJobStatus | null | undefined,
): number {
  if (!status) return 0;
  if (status.status === "completed") return 100;
  if (status.status === "failed") return 100;
  const stage = status.current_stage ?? status.metadata?.current_stage ?? "queued";
  const discovery = status.discovery;
  if (stage === "discovery" && discovery && discovery.total > 0) {
    return 10 + Math.round((discovery.done / discovery.total) * 25);
  }
  if (stage === "dispatching") return 8;
  if (stage === "discovery") return 20;
  if (stage === "scrape") return 55;
  if (stage === "persist") return 88;
  return 12;
}

function isActivityStale(lastActivityAt: string | null | undefined): boolean {
  if (!lastActivityAt) return false;
  const ts = new Date(lastActivityAt).getTime();
  if (Number.isNaN(ts)) return false;
  return (Date.now() - ts) / 1000 > STALE_ACTIVITY_SECONDS;
}

function marketplaceScopeLabel(
  run: ParsingPipelineRun,
  t: (key: string, opts?: Record<string, unknown>) => string,
): string {
  if (run.marketplace_codes?.length) {
    return t("admin.dataCollection.scopeSelected", { count: run.marketplace_codes.length });
  }
  return t("admin.dataCollection.scopeAll");
}

interface DataCollectionTabProps {
  onOpenRunDetails: (jobId: string) => void;
}

/**
 * Admin Data Collection tab: manual full-pool runs, scoped runs, live monitor, history.
 */
export function DataCollectionTab({ onOpenRunDetails }: DataCollectionTabProps) {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const locale = i18n.resolvedLanguage || "en";
  const dash = t("common.dash");

  const [selectedCodes, setSelectedCodes] = useState<Set<string>>(new Set());
  const [monitorJobId, setMonitorJobId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const previousActiveStatus = useRef<"running" | "completed" | "failed" | null>(null);
  const marketplaceSelectionInitialized = useRef(false);

  const activeJobQuery = useParsingActiveJob(4000);
  const marketplacesQuery = useParsingMarketplacesDetailed(500);
  const runsQuery = useParsingPipelineRuns(RUNS_LIMIT);
  const runPipeline = useRunParsingPipeline();
  const cancelJob = useCancelParsingActiveJob();

  const activeJobId = activeJobQuery.data?.active_job?.job_id ?? null;

  useEffect(() => {
    if (activeJobId) {
      setMonitorJobId(activeJobId);
    }
  }, [activeJobId]);

  const monitorStatusQuery = useParsingJobStatus(monitorJobId, {
    enabled: Boolean(monitorJobId),
    refetchInterval: monitorJobId ? 2000 : false,
  });

  const monitorStatus = monitorStatusQuery.data;
  const currentStage =
    monitorStatus?.current_stage ?? monitorStatus?.metadata?.current_stage ?? null;
  const showScrapeMonitor =
    currentStage === "scrape" ||
    currentStage === "persist" ||
    monitorStatus?.status === "completed";

  const liveFeedQuery = useParsingJobLiveFeed(monitorJobId, {
    enabled: Boolean(monitorJobId) && showScrapeMonitor,
    refetchInterval: showScrapeMonitor && monitorStatus?.status === "running" ? 3000 : false,
    limit: 300,
    offset: 0,
  });

  const liveFeed = liveFeedQuery.data;
  const progress = computeProgress(monitorStatus);
  const discovery = monitorStatus?.discovery;
  const summary = monitorStatus?.metadata?.summary;
  const lastActivityAt = monitorStatus?.metadata?.last_activity_at;
  const activityStale =
    monitorStatus?.status === "running" && isActivityStale(lastActivityAt);

  const activeMarketplaces = useMemo(
    () => (marketplacesQuery.data ?? []).filter((mp) => mp.is_active),
    [marketplacesQuery.data],
  );

  useEffect(() => {
    if (marketplaceSelectionInitialized.current || activeMarketplaces.length === 0) return;
    marketplaceSelectionInitialized.current = true;
    setSelectedCodes(new Set(activeMarketplaces.map((mp) => mp.marketplace_code)));
  }, [activeMarketplaces]);

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
    const status = monitorStatus?.status;
    if (!status) return;
    if (previousActiveStatus.current === "running" && status !== "running") {
      void queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "pipeline-runs"] });
      void queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "active-job"] });
      if (status === "completed") {
        toast.success(t("admin.dataCollection.runCompleted"));
      } else if (status === "failed") {
        toast.error(t("admin.dataCollection.runFailed"));
      }
    }
    previousActiveStatus.current = status;
  }, [monitorStatus?.status, queryClient, t]);

  const elapsedSeconds = useMemo(() => {
    const started = monitorStatus?.started_at ?? liveFeed?.started_at;
    if (!started) return null;
    const start = new Date(started).getTime();
    if (Number.isNaN(start)) return null;
    const endIso = monitorStatus?.completed_at ?? liveFeed?.completed_at;
    const end = endIso ? new Date(endIso).getTime() : Date.now();
    if (Number.isNaN(end) || end < start) return null;
    return (end - start) / 1000;
  }, [monitorStatus, liveFeed]);

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
      if (step.status === "success") existing.success += 1;
      else existing.failed += 1;
      grouped.set(key, existing);
    }
    return Array.from(grouped.entries()).map(([marketplace, values]) => ({
      marketplace,
      ...values,
    }));
  }, [liveFeed?.steps]);

  const throughputTimeline = useMemo(() => {
    const bucket = new Map<
      string,
      { minuteLabel: string; steps: number; success: number; failed: number }
    >();
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
      if (step.status === "success") row.success += 1;
      else row.failed += 1;
      bucket.set(minuteKey, row);
    }
    return Array.from(bucket.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([, value]) => value);
  }, [liveFeed?.steps]);

  const toggleMarketplace = (code: string, checked: boolean) => {
    setSelectedCodes((prev) => {
      const next = new Set(prev);
      if (checked) next.add(code);
      else next.delete(code);
      return next;
    });
  };

  const selectAllMarketplaces = () => {
    setSelectedCodes(new Set(activeMarketplaces.map((mp) => mp.marketplace_code)));
  };

  const clearMarketplaceSelection = () => {
    setSelectedCodes(new Set());
  };

  const launchFullCollection = async () => {
    try {
      const result = await runPipeline.mutateAsync(undefined);
      setMonitorJobId(result.job_id);
      toast.success(t("admin.dataCollection.fullRunStarted"));
    } catch (error) {
      toast.error(extractMutationError(error, t("admin.markets.refreshError")));
    }
  };

  const launchSelectedCollection = async () => {
    const codes = Array.from(selectedCodes);
    if (codes.length === 0) {
      toast.error(t("admin.dataCollection.selectAtLeastOne"));
      return;
    }
    try {
      const result = await runPipeline.mutateAsync({ marketplace_codes: codes });
      setMonitorJobId(result.job_id);
      toast.success(t("admin.dataCollection.scopedRunStarted", { count: codes.length }));
    } catch (error) {
      toast.error(extractMutationError(error, t("admin.markets.refreshError")));
    }
  };

  const onCancelActive = async () => {
    try {
      await cancelJob.mutateAsync();
      await queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "active-job"] });
      toast.success(t("admin.dataCollection.runCancelled"));
    } catch (error) {
      toast.error(extractMutationError(error, t("admin.markets.refreshError")));
    }
  };

  const perMarketplaceRows = monitorStatus?.metadata?.per_marketplace ?? [];
  const scopedMarketplaceCodes = monitorStatus?.metadata?.marketplace_codes ?? [];
  const discoveryErrors = Array.isArray(monitorStatus?.metadata?.discovery_errors)
    ? (monitorStatus?.metadata?.discovery_errors as string[])
    : [];
  const celeryTaskId =
    typeof monitorStatus?.metadata?.celery_task_id === "string"
      ? monitorStatus.metadata.celery_task_id
      : null;
  const discoveryInProgress =
    monitorStatus?.status === "running" &&
    (currentStage === "discovery" || currentStage === "dispatching");

  return (
    <div className="space-y-6">
      <Card>
        <CardHeader className="space-y-3">
          <CardTitle>{t("admin.dataCollection.title")}</CardTitle>
          <CardDescription>{t("admin.dataCollection.description")}</CardDescription>
          <div className="flex flex-wrap gap-2">
            <Button
              size="lg"
              onClick={() => void launchFullCollection()}
              disabled={runPipeline.isPending || Boolean(activeJobId)}
            >
              {runPipeline.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Play className="mr-2 size-4" />
              )}
              {t("admin.dataCollection.runFull")}
            </Button>
            <Button
              size="lg"
              variant="secondary"
              onClick={() => void launchSelectedCollection()}
              disabled={runPipeline.isPending || Boolean(activeJobId) || selectedCodes.size === 0}
            >
              <Play className="mr-2 size-4" />
              {t("admin.dataCollection.runSelected", { count: selectedCodes.size })}
            </Button>
            {activeJobId ? (
              <Button
                size="lg"
                variant="outline"
                onClick={() => void onCancelActive()}
                disabled={cancelJob.isPending}
              >
                {cancelJob.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Square className="mr-2 size-4" />
                )}
                {t("admin.dataCollection.cancelRun")}
              </Button>
            ) : null}
            {monitorJobId ? (
              <Badge variant="secondary" className="self-center font-mono text-xs">
                {monitorJobId.slice(0, 8)}…
              </Badge>
            ) : null}
          </div>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex flex-wrap items-center justify-between gap-2">
            <p className="text-sm font-medium">{t("admin.dataCollection.marketplacePicker")}</p>
            <div className="flex gap-2">
              <Button type="button" variant="outline" size="sm" onClick={selectAllMarketplaces}>
                {t("admin.dataCollection.selectAll")}
              </Button>
              <Button type="button" variant="ghost" size="sm" onClick={clearMarketplaceSelection}>
                {t("admin.dataCollection.clearSelection")}
              </Button>
            </div>
          </div>
          {marketplacesQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : (
            <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 lg:grid-cols-3">
              {activeMarketplaces.map((mp) => {
                const checked = selectedCodes.has(mp.marketplace_code);
                return (
                  <label
                    key={mp.id}
                    className="flex cursor-pointer items-start gap-3 rounded-md border p-3 hover:bg-muted/40"
                  >
                    <Checkbox
                      checked={checked}
                      onCheckedChange={(value) =>
                        toggleMarketplace(mp.marketplace_code, value === true)
                      }
                    />
                    <span className="min-w-0 flex-1">
                      <span className="block font-medium">{mp.name}</span>
                      <span className="block truncate text-xs text-muted-foreground">
                        {mp.domain} · {mp.marketplace_code}
                      </span>
                    </span>
                  </label>
                );
              })}
            </div>
          )}
        </CardContent>
      </Card>

      {activeJobId && !monitorJobId ? (
        <Card className="border-primary/40">
          <CardContent className="flex items-center gap-3 pt-6 text-sm">
            <Loader2 className="size-5 animate-spin text-primary" />
            {t("admin.dataCollection.loadingActiveJob")}
          </CardContent>
        </Card>
      ) : null}

      {monitorJobId ? (
        <Card id="pipeline-live-monitor" className={activeJobId ? "border-primary/50" : undefined}>
          <CardHeader className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <CardTitle>{t("admin.dataCollection.liveMonitor")}</CardTitle>
              {monitorStatus ? (
                <Badge variant={statusBadgeVariant(monitorStatus.status)}>
                  {t(statusLabelKey(monitorStatus.status))}
                </Badge>
              ) : null}
            </div>
            <CardDescription>
              {t(stageLabelKey(currentStage))}
              {discovery?.total
                ? ` · ${t("admin.dataCollection.discoveryProgress", {
                    done: discovery.done,
                    total: discovery.total,
                  })}`
                : ""}
              {discovery?.current_domain
                ? ` · ${discovery.current_domain}`
                : ""}
            </CardDescription>
          </CardHeader>
          <CardContent className="space-y-4">
            {monitorStatusQuery.isLoading ? (
              <Skeleton className="h-32 w-full" />
            ) : (
              <>
                <Progress value={progress} max={100} />
                {activityStale ? (
                  <div className="flex items-center gap-2 rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm text-amber-800 dark:text-amber-200">
                    <AlertTriangle className="size-4 shrink-0" />
                    {t("admin.dataCollection.staleActivity", {
                      at: formatDateTime(lastActivityAt ?? null, locale, dash),
                    })}
                  </div>
                ) : null}
                <div className="grid grid-cols-2 gap-3 md:grid-cols-4 xl:grid-cols-6">
                  <MetricTile
                    label={t("admin.dataCollection.metric.stage")}
                    value={t(stageLabelKey(currentStage))}
                  />
                  <MetricTile
                    label={t("admin.marketplaces.products")}
                    value={String(summary?.listings_created ?? 0)}
                  />
                  <MetricTile
                    label={t("common.price")}
                    value={String(summary?.prices_saved ?? 0)}
                  />
                  <MetricTile
                    label={t("admin.stats.errors")}
                    value={String(summary?.errors_count ?? 0)}
                  />
                  <MetricTile
                    label={t("admin.dataCollection.metric.elapsed")}
                    value={formatDuration(elapsedSeconds, dash)}
                    icon={<Timer className="size-4 text-primary" />}
                  />
                  <MetricTile
                    label={t("admin.dataCollection.metric.scrapeSteps")}
                    value={String(liveFeed?.total_steps ?? 0)}
                    icon={<Gauge className="size-4 text-primary" />}
                  />
                </div>

                <Tabs defaultValue="discovery" className="space-y-4">
                  <TabsList>
                    <TabsTrigger value="discovery">
                      {t("admin.dataCollection.tab.discovery")}
                    </TabsTrigger>
                    <TabsTrigger value="scrape">{t("admin.dataCollection.tab.scrape")}</TabsTrigger>
                    <TabsTrigger value="summary">{t("admin.dataCollection.tab.summary")}</TabsTrigger>
                  </TabsList>

                  <TabsContent value="discovery" className="space-y-3">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div className="rounded-md border p-3 text-sm">
                        <p className="text-muted-foreground">{t("admin.dataCollection.scopeLabel")}</p>
                        <p className="font-medium">
                          {scopedMarketplaceCodes.length
                            ? scopedMarketplaceCodes.join(", ")
                            : t("admin.dataCollection.scopeAll")}
                        </p>
                      </div>
                      <div className="rounded-md border p-3 text-sm">
                        <p className="text-muted-foreground">{t("admin.dataCollection.lastActivity")}</p>
                        <p className="font-medium">
                          {formatDateTime(lastActivityAt ?? null, locale, dash)}
                        </p>
                      </div>
                      {celeryTaskId ? (
                        <div className="rounded-md border p-3 text-sm md:col-span-2">
                          <p className="text-muted-foreground">Celery task</p>
                          <p className="font-mono text-xs">{celeryTaskId}</p>
                        </div>
                      ) : null}
                    </div>
                    {discoveryInProgress && discovery?.current_domain ? (
                      <div className="flex items-center gap-2 rounded-md border border-primary/30 bg-primary/5 p-3 text-sm">
                        <Loader2 className="size-4 animate-spin text-primary" />
                        {t("admin.dataCollection.discoveryInProgress", {
                          domain: discovery.current_domain,
                          done: discovery.done,
                          total: discovery.total,
                        })}
                      </div>
                    ) : null}
                    {discoveryErrors.length > 0 ? (
                      <div className="rounded-md border border-amber-500/40 bg-amber-500/10 p-3 text-sm">
                        <p className="mb-2 font-medium text-amber-800 dark:text-amber-200">
                          {t("admin.dataCollection.discoveryErrors")}
                        </p>
                        <ul className="list-inside list-disc space-y-1 text-amber-900/90 dark:text-amber-100/90">
                          {discoveryErrors.slice(0, 10).map((err) => (
                            <li key={err} className="break-all">
                              {err}
                            </li>
                          ))}
                        </ul>
                      </div>
                    ) : null}
                    {perMarketplaceRows.length === 0 && !discoveryInProgress ? (
                      <EmptyState
                        title={t("common.noData")}
                        description={t("admin.dataCollection.discoveryEmpty")}
                      />
                    ) : (
                      <Table>
                        <TableHeader>
                          <TableRow>
                            <TableHead>{t("products.marketplace")}</TableHead>
                            <TableHead>{t("admin.marketplaces.products")}</TableHead>
                            <TableHead>{t("admin.stats.errors")}</TableHead>
                            <TableHead>{t("admin.claude.avgLatency")}</TableHead>
                            <TableHead>{t("common.status")}</TableHead>
                          </TableRow>
                        </TableHeader>
                        <TableBody>
                          {discoveryInProgress &&
                          discovery?.current_domain &&
                          !perMarketplaceRows.some((row) => row.domain === discovery.current_domain) ? (
                            <TableRow className="bg-primary/5">
                              <TableCell>{discovery.current_domain}</TableCell>
                              <TableCell>{dash}</TableCell>
                              <TableCell>{dash}</TableCell>
                              <TableCell>{dash}</TableCell>
                              <TableCell>
                                <Badge variant="secondary">{t("common.loading")}</Badge>
                              </TableCell>
                            </TableRow>
                          ) : null}
                          {perMarketplaceRows.map((row) => (
                            <TableRow key={row.marketplace_id}>
                              <TableCell>{row.domain ?? row.marketplace_id.slice(0, 8)}</TableCell>
                              <TableCell>{row.listings_created}</TableCell>
                              <TableCell>{row.errors_count}</TableCell>
                              <TableCell>{row.duration_ms} ms</TableCell>
                              <TableCell>
                                <Badge variant={statusBadgeVariant(row.status)}>{row.status}</Badge>
                              </TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    )}
                  </TabsContent>

                  <TabsContent value="scrape" className="space-y-4">
                    {!showScrapeMonitor ? (
                      <EmptyState
                        title={t("admin.dataCollection.scrapeNotStarted")}
                        description={t("admin.dataCollection.scrapeNotStartedHint")}
                      />
                    ) : (
                      <>
                        <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
                          <ChartCard title={t("admin.dataCollection.chart.status")}>
                            {statusPieData.length === 0 ? (
                              <EmptyState title={t("common.noData")} description="" />
                            ) : (
                              <ResponsiveContainer width="100%" height={240}>
                                <PieChart>
                                  <Pie data={statusPieData} dataKey="value" nameKey="name" outerRadius={90} label>
                                    {statusPieData.map((entry, idx) => (
                                      <Cell
                                        key={`${entry.name}-${idx}`}
                                        fill={
                                          entry.name === "success"
                                            ? "#16a34a"
                                            : entry.name === "missing_critical_data"
                                              ? "#f59e0b"
                                              : "#ef4444"
                                        }
                                      />
                                    ))}
                                  </Pie>
                                  <Tooltip />
                                </PieChart>
                              </ResponsiveContainer>
                            )}
                          </ChartCard>
                          <ChartCard title={t("admin.dataCollection.chart.marketplaces")}>
                            {stepsByMarketplace.length === 0 ? (
                              <EmptyState title={t("common.noData")} description="" />
                            ) : (
                              <ResponsiveContainer width="100%" height={240}>
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
                          </ChartCard>
                        </div>
                        <ChartCard title={t("admin.dataCollection.liveLog")}>
                          {liveFeedQuery.isLoading ? (
                            <Skeleton className="h-48 w-full" />
                          ) : (liveFeed?.steps.length ?? 0) === 0 ? (
                            <EmptyState
                              title={t("common.noData")}
                              description={t("admin.dataCollection.liveLogDescription")}
                            />
                          ) : (
                            <div className="max-h-80 overflow-auto">
                              <Table>
                                <TableHeader>
                                  <TableRow>
                                    <TableHead>{t("alerts.date")}</TableHead>
                                    <TableHead>{t("products.marketplace")}</TableHead>
                                    <TableHead>{t("common.status")}</TableHead>
                                    <TableHead>{t("common.price")}</TableHead>
                                    <TableHead>URL</TableHead>
                                  </TableRow>
                                </TableHeader>
                                <TableBody>
                                  {liveFeed?.steps.map((step) => (
                                    <TableRow key={step.event_id}>
                                      <TableCell>
                                        {formatDateTime(step.created_at, locale, dash)}
                                      </TableCell>
                                      <TableCell>
                                        {step.marketplace_domain || step.marketplace_id.slice(0, 8)}
                                      </TableCell>
                                      <TableCell>{step.status}</TableCell>
                                      <TableCell>{step.price_found ?? dash}</TableCell>
                                      <TableCell className="max-w-xs truncate">{step.url}</TableCell>
                                    </TableRow>
                                  ))}
                                </TableBody>
                              </Table>
                            </div>
                          )}
                        </ChartCard>
                      </>
                    )}
                  </TabsContent>

                  <TabsContent value="summary" className="space-y-3">
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div className="rounded-md border p-3 text-sm">
                        <p className="text-muted-foreground">{t("admin.dataCollection.scopeLabel")}</p>
                        <p className="font-medium">
                          {monitorStatus?.metadata?.marketplace_codes?.length
                            ? monitorStatus.metadata.marketplace_codes.join(", ")
                            : t("admin.dataCollection.scopeAll")}
                        </p>
                      </div>
                      <div className="rounded-md border p-3 text-sm">
                        <p className="text-muted-foreground">{t("admin.dataCollection.timings")}</p>
                        <p>
                          {t("admin.pool.triggerDiscovery")}:{" "}
                          {monitorStatus?.metadata?.timings?.discovery_ms ?? 0} ms
                        </p>
                        <p>
                          {t("admin.pool.triggerScraping")}:{" "}
                          {monitorStatus?.metadata?.timings?.scrape_ms ?? 0} ms
                        </p>
                        <p>
                          {t("admin.dataCollection.total")}:{" "}
                          {monitorStatus?.metadata?.timings?.total_ms ?? 0} ms
                        </p>
                      </div>
                    </div>
                    {monitorStatus?.metadata?.error ? (
                      <div className="rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
                        {monitorStatus.metadata.error}
                      </div>
                    ) : null}
                    <Button variant="outline" onClick={() => onOpenRunDetails(monitorJobId)}>
                      {t("admin.dataCollection.openDetails")}
                    </Button>
                  </TabsContent>
                </Tabs>
              </>
            )}
          </CardContent>
        </Card>
      ) : null}

      <Card>
        <CardHeader>
          <CardTitle>{t("admin.dataCollection.runHistory")}</CardTitle>
          <CardDescription>{t("admin.dataCollection.runHistoryHint")}</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {runsQuery.isLoading ? (
            <Skeleton className="h-56 w-full" />
          ) : pagedRuns.length === 0 ? (
            <EmptyState title={t("common.noData")} description={t("admin.dataCollection.runHistory")} />
          ) : (
            <>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Job</TableHead>
                    <TableHead>{t("alerts.date")}</TableHead>
                    <TableHead>{t("admin.dataCollection.scopeLabel")}</TableHead>
                    <TableHead>{t("admin.dataCollection.metric.stage")}</TableHead>
                    <TableHead>{t("admin.marketplaces.products")}</TableHead>
                    <TableHead>{t("common.price")}</TableHead>
                    <TableHead>{t("admin.stats.errors")}</TableHead>
                    <TableHead>{t("common.status")}</TableHead>
                    <TableHead>{t("admin.dataCollection.errorColumn")}</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  {pagedRuns.map((run) => (
                    <TableRow
                      key={run.job_id}
                      className="cursor-pointer"
                      data-selected={monitorJobId === run.job_id}
                      onClick={() => {
                        setMonitorJobId(run.job_id);
                        onOpenRunDetails(run.job_id);
                      }}
                    >
                      <TableCell>
                        <button
                          type="button"
                          className="inline-flex items-center gap-1 text-primary hover:underline"
                          onClick={(event) => {
                            event.stopPropagation();
                            void navigator.clipboard.writeText(run.job_id);
                            toast.success(t("common.copied"));
                          }}
                        >
                          <Copy className="size-3.5" />
                          {run.job_id.slice(0, 8)}…
                        </button>
                      </TableCell>
                      <TableCell>{formatDateTime(run.started_at, locale, dash)}</TableCell>
                      <TableCell className="max-w-40 truncate">
                        {marketplaceScopeLabel(run, t)}
                      </TableCell>
                      <TableCell>{run.current_stage ? t(stageLabelKey(run.current_stage)) : dash}</TableCell>
                      <TableCell>
                        {run.summary_pending ? dash : run.listings_created}
                      </TableCell>
                      <TableCell>{run.summary_pending ? dash : run.prices_saved}</TableCell>
                      <TableCell>{run.summary_pending ? dash : run.errors_count}</TableCell>
                      <TableCell>
                        <Badge variant={statusBadgeVariant(run.status)}>
                          {t(statusLabelKey(run.status))}
                        </Badge>
                      </TableCell>
                      <TableCell className="max-w-xs truncate text-xs text-muted-foreground">
                        {run.error_message ?? dash}
                      </TableCell>
                    </TableRow>
                  ))}
                </TableBody>
              </Table>
              <div className="flex items-center justify-between">
                <p className="text-sm text-muted-foreground">
                  {historyPage}/{totalPages}
                </p>
                <div className="flex gap-2">
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={historyPage <= 1}
                    onClick={() => setHistoryPage((p) => Math.max(1, p - 1))}
                  >
                    {t("common.back")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={historyPage >= totalPages}
                    onClick={() => setHistoryPage((p) => Math.min(totalPages, p + 1))}
                  >
                    {t("common.next")}
                  </Button>
                </div>
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  );
}

function extractMutationError(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error &&
    "response" in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail ===
      "string"
  ) {
    return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? fallback;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function MetricTile({
  label,
  value,
  icon,
}: {
  label: string;
  value: string;
  icon?: ReactNode;
}) {
  return (
    <div className="rounded-md border p-3">
      <p className="text-xs text-muted-foreground">{label}</p>
      <p className="mt-1 flex items-center gap-2 text-lg font-semibold">
        {icon}
        {value}
      </p>
    </div>
  );
}

function ChartCard({ title, children }: { title: string; children: ReactNode }) {
  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">{title}</CardTitle>
      </CardHeader>
      <CardContent>{children}</CardContent>
    </Card>
  );
}
