import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import { Clock3, Copy, Loader2, Play } from "lucide-react";
import { toast } from "sonner";
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
  useAdminStats,
  useParsingJobLiveFeed,
  useParsingMarketplacesDetailed,
  useParsingJobStatus,
  useParsingTestMarketplaces,
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

function marketplaceActivityLabelKey(status: "running" | "completed" | "failed"): string {
  return status === "running" ? "admin.claude.online" : "admin.marketplaces.status.noData";
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

  const { data: stats } = useAdminStats();
  const marketplacesQuery = useParsingTestMarketplaces();
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

  const activeStatus = activeStatusQuery.data;
  const detailsStatus = detailsStatusQuery.data;
  const currentStage = activeStatus?.current_stage ?? "queued";
  const progress = stageToProgress(currentStage, activeStatus?.status ?? "running");

  return (
    <div className="space-y-6">
      <PageHeader title="nav.admin" />

      <Tabs defaultValue="parsing" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">{t("dashboard.market.title")}</TabsTrigger>
          <TabsTrigger value="parsing">{t("admin.pool.title")}</TabsTrigger>
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
                <p className="text-2xl font-semibold">
                  {stats?.marketplaces_count ?? stats?.marketplaces ?? 0}
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.marketplaces.products")}</p>
                <p className="text-2xl font-semibold">{stats?.total_products_monitored ?? 0}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="parsing" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>{t("admin.pool.title")}</CardTitle>
              <CardDescription>
                Подробные вкладки: pipeline, users, marketplaces и live-пошаговый трекинг.
              </CardDescription>
            </CardHeader>
          </Card>

          <Tabs defaultValue="pipeline" className="space-y-4">
            <TabsList>
              <TabsTrigger value="pipeline">Pipeline</TabsTrigger>
              <TabsTrigger value="users">Users</TabsTrigger>
              <TabsTrigger value="marketplaces">Marketplaces</TabsTrigger>
              <TabsTrigger value="live">Live steps</TabsTrigger>
            </TabsList>

            <TabsContent value="pipeline" className="space-y-6">
              <Card>
                <CardHeader className="space-y-3">
                  <CardTitle>{t("admin.pool.triggerScraping")}</CardTitle>
                  <CardDescription>{t("admin.pool.diagnosticsResult")}</CardDescription>
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
                    {t("admin.pool.triggerScraping")}
                  </Button>
                </CardHeader>
                <CardContent>
                  {activeJobId && activeStatus ? (
                    <div className="space-y-4 rounded-lg border p-4">
                      <div className="flex flex-wrap items-center gap-2">
                        <Badge variant={statusBadgeVariant(activeStatus.status)}>
                          {t(statusLabelKey(activeStatus.status))}
                        </Badge>
                        <span className="text-sm text-muted-foreground">{activeStatus.job_id}</span>
                      </div>
                      <Progress value={progress} max={100} />
                      <div className="grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-3">
                        <span>{t("admin.pool.triggerDiscovery")}: {currentStage === "discovery" ? t("common.loading") : t("common.noData")}</span>
                        <span>{t("admin.pool.triggerScraping")}: {currentStage === "scrape" ? t("common.loading") : t("common.noData")}</span>
                        <span>{t("admin.pool.diagnostics")}: {currentStage === "persist" ? t("common.loading") : t("common.noData")}</span>
                      </div>
                    </div>
                  ) : (
                    <EmptyState title={t("common.noData")} description={t("admin.pool.triggerScraping")} />
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
                          <Button variant="outline" size="sm" onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))} disabled={historyPage <= 1}>
                            {t("common.back")}
                          </Button>
                          <Button variant="outline" size="sm" onClick={() => setHistoryPage((prev) => Math.min(totalPages, prev + 1))} disabled={historyPage >= totalPages}>
                            {t("common.next")}
                          </Button>
                        </div>
                      </div>
                    </>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="users">
              <Card>
                <CardHeader>
                  <CardTitle>Users details</CardTitle>
                  <CardDescription>Полная таблица пользователей с активностью и нагрузкой.</CardDescription>
                </CardHeader>
                <CardContent>
                  {usersDetailedQuery.isLoading ? (
                    <Skeleton className="h-56 w-full" />
                  ) : (usersDetailedQuery.data?.length ?? 0) === 0 ? (
                    <EmptyState title={t("common.noData")} description="Users details" />
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

            <TabsContent value="marketplaces">
              <Card>
                <CardHeader>
                  <CardTitle>Marketplaces details</CardTitle>
                  <CardDescription>Детальная телеметрия по каждому маркетплейсу и discovery/scrape состоянию.</CardDescription>
                </CardHeader>
                <CardContent>
                  {marketplacesDetailedQuery.isLoading ? (
                    <Skeleton className="h-56 w-full" />
                  ) : (marketplacesDetailedQuery.data?.length ?? 0) === 0 ? (
                    <EmptyState title={t("common.noData")} description="Marketplaces details" />
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Domain</TableHead>
                          <TableHead>Quota</TableHead>
                          <TableHead>Pool</TableHead>
                          <TableHead>Active listings</TableHead>
                          <TableHead>Success rate</TableHead>
                          <TableHead>Last discovery</TableHead>
                          <TableHead>Last scrape</TableHead>
                          <TableHead>Last error</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {marketplacesDetailedQuery.data?.map((mp) => (
                          <TableRow key={mp.id}>
                            <TableCell>{mp.domain}</TableCell>
                            <TableCell>{mp.product_quota}</TableCell>
                            <TableCell>{mp.products_in_pool}</TableCell>
                            <TableCell>{mp.active_listings}</TableCell>
                            <TableCell>{mp.success_rate.toFixed(2)}%</TableCell>
                            <TableCell>{formatDateTime(mp.last_discovery_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                            <TableCell>{formatDateTime(mp.last_scrape_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                            <TableCell className="max-w-80 truncate">{mp.last_error_message || t("common.dash")}</TableCell>
                          </TableRow>
                        ))}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </TabsContent>

            <TabsContent value="live">
              <Card>
                <CardHeader>
                  <CardTitle>Live process feed</CardTitle>
                  <CardDescription>Пошаговый realtime-поток по `scrape_logs` для выбранного job.</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <p className="text-sm text-muted-foreground">
                      Job: {liveJobId ?? t("common.dash")}
                    </p>
                    {liveFeedQuery.data && (
                      <>
                        <Badge variant={statusBadgeVariant(liveFeedQuery.data.status)}>
                          {t(statusLabelKey(liveFeedQuery.data.status))}
                        </Badge>
                        <span className="text-sm text-muted-foreground">
                          {liveFeedQuery.data.current_stage || "queued"} | steps: {liveFeedQuery.data.total_steps}
                        </span>
                      </>
                    )}
                  </div>

                  {liveFeedQuery.isLoading ? (
                    <Skeleton className="h-56 w-full" />
                  ) : !liveFeedQuery.data ? (
                    <EmptyState title={t("common.noData")} description="Live process feed" />
                  ) : (
                    <>
                      <div className="flex flex-wrap gap-2">
                        {Object.entries(liveFeedQuery.data.status_counts).map(([statusKey, count]) => (
                          <Badge key={statusKey} variant={statusKey === "success" ? "default" : "secondary"}>
                            {statusKey}: {count}
                          </Badge>
                        ))}
                      </div>
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
                          {liveFeedQuery.data.steps.map((step) => (
                            <TableRow key={step.event_id}>
                              <TableCell>{formatDateTime(step.created_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                              <TableCell>{step.marketplace_domain || step.marketplace_id.slice(0, 8)}</TableCell>
                              <TableCell>{step.status}</TableCell>
                              <TableCell>{step.duration_ms ?? t("common.dash")}</TableCell>
                              <TableCell>{step.price_found ?? t("common.dash")}</TableCell>
                              <TableCell className="max-w-72 truncate">{step.url}</TableCell>
                              <TableCell className="max-w-80 truncate">{step.error_message || t("common.dash")}</TableCell>
                            </TableRow>
                          ))}
                        </TableBody>
                      </Table>
                    </>
                  )}
                </CardContent>
              </Card>
            </TabsContent>
          </Tabs>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>{t("admin.pool.marketplaces")}</CardTitle>
                <CardDescription>{t("admin.marketplaces.successRate")}</CardDescription>
              </div>
            </CardHeader>
            <CardContent>
              {marketplacesQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (marketplacesQuery.data?.length ?? 0) === 0 ? (
                <EmptyState title={t("common.noData")} description={t("admin.pool.marketplaces")} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("products.marketplace")}</TableHead>
                      <TableHead>{t("competitors.tableUrl")}</TableHead>
                      <TableHead>{t("admin.pool.productsInPool")}</TableHead>
                      <TableHead>{t("admin.marketplaces.lastScrape")}</TableHead>
                      <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                      <TableHead>{t("admin.markets.lastRefresh")}</TableHead>
                      <TableHead>{t("common.status")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {marketplacesQuery.data?.map((item) => (
                      <TableRow key={item.url}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="max-w-60 truncate">{item.url}</TableCell>
                        <TableCell>{item.products_in_pool}</TableCell>
                        <TableCell>{formatDateTime(item.last_successful_scrape, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{item.success_rate.toFixed(2)}%</TableCell>
                        <TableCell>{formatDateTime(item.last_run, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant(item.status)}>
                            {t(marketplaceActivityLabelKey(item.status))}
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
