// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Administration page for superusers.
 * Stats, Claude API status, add marketplace, scrape activity, error distribution,
 * marketplace table, users table.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import {
  Users,
  Store,
  Activity,
  AlertTriangle,
  Brain,
  Loader2,
  Plus,
  Trash2,
  ChevronDown,
  ChevronRight,
  RefreshCw,
  Stethoscope,
  Calculator,
  Play,
  Scissors,
  Merge,
} from "lucide-react";
import { toast } from "sonner";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  Legend,
  ResponsiveContainer,
  PieChart,
  Pie,
  Cell,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import {
  Tooltip as TooltipRoot,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import {
  useAdminStats,
  useAdminMarketplaces,
  useMarketplaceLogs,
  useScrapeActivity,
  useErrorDistribution,
  useAdminUsers,
  useClaudeStatus,
  useAddMarketplace,
  useDeleteMarketplace,
  useMarketsIngest,
  useApiHealth,
} from "@/hooks/useAdmin";
import {
  runPoolDiagnostics,
  recalculateQuotas,
  triggerDiscoveryAll,
  triggerPoolScrape,
  clearUserProducts,
  cleanupInvalidProducts,
  clearPool,
  deduplicateMarketplaces,
  type PoolDiagnostics,
} from "@/api/admin";
import { formatRelativeTime } from "@/lib/formatters";
import type { AdminMarketplace as AdminMarketplaceType } from "@/api/admin";
import { marketsApi, marketsQueryKeys } from "@/api/markets";

function getCountryFlag(country: string): string {
  switch (country) {
    case "RU":
      return "🇷🇺";
    case "KZ":
      return "🇰🇿";
    case "BY":
      return "🇧🇾";
    case "UA":
      return "🇺🇦";
    case "DE":
      return "🇩🇪";
    case "PL":
      return "🇵🇱";
    case "XX":
      return "🌐";
    default:
      return country;
  }
}

function ClaudeStatusCard() {
  const { t, i18n } = useTranslation();
  const { data, isLoading, refetch, isFetching } = useClaudeStatus();
  const [expanded, setExpanded] = useState(false);

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader className="pb-2">
          <Skeleton className="h-4 w-24" />
        </CardHeader>
        <CardContent>
          <Skeleton className="h-8 w-16" />
        </CardContent>
      </Card>
    );
  }

  const health = data.health;
  const stats = data.stats;

  if (!health && !stats) {
    return (
      <Card>
        <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
          <p className="text-sm font-medium text-muted-foreground">
            {t("admin.claude.title")}
          </p>
          <Brain className="size-4 shrink-0 text-muted-foreground" />
        </CardHeader>
        <CardContent>
          <div className="text-2xl font-bold">
            {data.configured
              ? t("admin.claude.configured", { model: data.model ?? "—" })
              : t("admin.claude.notConfigured")}
          </div>
          <Button
            size="sm"
            variant="outline"
            onClick={(e) => {
              e.stopPropagation();
              refetch();
            }}
            disabled={isFetching}
            className="mt-2"
          >
            {isFetching ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}{" "}
            {t("admin.claude.checkNow")}
          </Button>
        </CardContent>
      </Card>
    );
  }

  const status = health?.status ?? "not_configured";

  const statusLabel =
    status === "online"
      ? t("admin.claude.online")
      : status === "error" || status === "auth_error"
        ? t("admin.claude.error")
        : status === "timeout"
          ? t("admin.claude.timeout")
          : status === "rate_limited"
            ? t("admin.claude.rateLimited")
            : status === "overloaded"
              ? t("admin.claude.overloaded")
              : status === "not_configured"
                ? t("admin.claude.notConfigured")
                : t("admin.claude.error");

  const dotColor =
    status === "online"
      ? "bg-green-500"
      : status === "error" || status === "auth_error"
        ? "bg-red-500"
        : status === "timeout" || status === "rate_limited" || status === "overloaded"
          ? "bg-[var(--color-promo)]"
          : "bg-muted-foreground";

  return (
    <Card
      className="cursor-pointer transition-colors hover:border-primary/30"
      onClick={() => setExpanded(!expanded)}
    >
      <CardHeader className="flex flex-row items-start justify-between space-y-0 pb-2">
        <p className="text-sm font-medium text-muted-foreground">
          {t("admin.claude.title")}
        </p>
        <div className="flex items-center gap-2">
          <span
            className={`inline-block size-2 rounded-full ${dotColor} ${status === "online" ? "animate-pulse" : ""}`}
          />
          <Brain className="size-4 shrink-0 text-muted-foreground" />
        </div>
      </CardHeader>
      <CardContent>
        <div className="text-2xl font-bold">{statusLabel}</div>
        <p className="text-xs text-muted-foreground">
          {t("admin.claude.latency", { ms: health?.latency_ms ?? 0 })}
        </p>
        {expanded && stats && (
          <div className="mt-4 space-y-2 border-t pt-4 text-xs">
            <p>
              {t("admin.claude.calls24h")}: {stats.calls_24h} (
              {stats.successful_24h} / {stats.failed_24h})
            </p>
            <p>
              {t("admin.claude.avgLatency")}: {stats.avg_latency_ms} ms
            </p>
            <p>
              {t("admin.claude.tokens24h")}: {stats.total_tokens_24h}
            </p>
            <p>
              {t("admin.claude.lastSuccess")}:{" "}
              {stats.last_success_at
                ? formatRelativeTime(stats.last_success_at, i18n.language || "en")
                : "—"}
            </p>
            {stats.last_error && (
              <p className="text-destructive">
                {t("admin.claude.lastError")}: {stats.last_error}
              </p>
            )}
            <Button
              size="sm"
              variant="outline"
              onClick={(e) => {
                e.stopPropagation();
                refetch();
              }}
              disabled={isFetching}
            >
              {isFetching ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}{" "}
              {t("admin.claude.checkNow")}
            </Button>
          </div>
        )}
      </CardContent>
    </Card>
  );
}

/**
 * Pool management workflow:
 * 1. Click "Диагностика пула" to see current state
 * 2. If quotas are 0 → click "Пересчитать квоты"
 * 3. Click "Запустить Discovery" → wait 5-10 min
 * 4. Click "Диагностика пула" again to check progress
 * 5. When products appear → click "Запустить Scraping"
 * 6. Check Dashboard → Market Overview should show products
 */
function PoolManagementCard() {
  const { t } = useTranslation();
  const [diagnostics, setDiagnostics] = useState<PoolDiagnostics | null>(null);
  const [loadingDiagnostics, setLoadingDiagnostics] = useState(false);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);

  const fetchDiagnostics = async () => {
    setLoadingDiagnostics(true);
    try {
      const { data } = await runPoolDiagnostics();
      setDiagnostics(data);
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingDiagnostics(false);
    }
  };

  const handleRecalculateQuotas = async () => {
    setLoadingAction("quotas");
    try {
      await recalculateQuotas();
      toast.success(t("admin.pool.quotasRecalculated"));
      await fetchDiagnostics();
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleTriggerDiscovery = async () => {
    setLoadingAction("discovery");
    try {
      await triggerDiscoveryAll();
      toast.success(t("admin.pool.discoveryLaunched"));
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleTriggerScrape = async () => {
    setLoadingAction("scrape");
    try {
      await triggerPoolScrape();
      toast.success(t("admin.pool.scrapingLaunched"));
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleClearUserProducts = async () => {
    if (!confirm(t("admin.pool.clearConfirm"))) {
      return;
    }
    setLoadingAction("clear");
    try {
      const { data } = await clearUserProducts();
      toast.success(t("admin.pool.clearedCount", { count: data.deleted_products }));
      await fetchDiagnostics();
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleCleanupInvalid = async () => {
    setLoadingAction("cleanup");
    try {
      const { data } = await cleanupInvalidProducts();
      const parts = [
        data.deleted_long_urls > 0 && `${data.deleted_long_urls} длинных URL`,
        data.deleted_invalid_urls > 0 && `${data.deleted_invalid_urls} невалидных`,
        (data.deleted_category_pages ?? 0) > 0 &&
          `${data.deleted_category_pages} страниц категорий`,
      ].filter(Boolean);
      toast.success(parts.length ? `Удалено: ${parts.join(", ")}` : "Нечего удалять");
      await fetchDiagnostics();
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleClearPool = async () => {
    if (!confirm("Удалить ВСЕ товары из пула? Запустите Discovery заново после этого.")) {
      return;
    }
    setLoadingAction("clearPool");
    try {
      const { data } = await clearPool();
      toast.success(`Пул очищен: удалено ${data.deleted} товаров`);
      await fetchDiagnostics();
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleDeduplicate = async () => {
    setLoadingAction("deduplicate");
    try {
      const { data } = await deduplicateMarketplaces();
      toast.success(`Объединено: ${data.merged} дубликатов`);
      await fetchDiagnostics();
    } catch {
      toast.error(t("common.error"));
    } finally {
      setLoadingAction(null);
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("admin.pool.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-4">
          <div className="flex flex-wrap gap-2">
            <Button
              variant="default"
              size="sm"
              onClick={fetchDiagnostics}
              disabled={loadingDiagnostics}
            >
              {loadingDiagnostics ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Stethoscope className="mr-2 size-4" />
              )}
              {t("admin.pool.diagnostics")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleRecalculateQuotas}
              disabled={loadingAction === "quotas"}
              className="border-amber-500 bg-amber-500/10 text-amber-700 hover:bg-amber-500/20 dark:text-amber-400 dark:hover:bg-amber-500/20"
            >
              {loadingAction === "quotas" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Calculator className="mr-2 size-4" />
              )}
              {t("admin.pool.recalculateQuotas")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleTriggerDiscovery}
              disabled={loadingAction === "discovery"}
              className="border-green-600 bg-green-600/10 text-green-700 hover:bg-green-600/20 dark:text-green-400 dark:hover:bg-green-600/20"
            >
              {loadingAction === "discovery" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Play className="mr-2 size-4" />
              )}
              {t("admin.pool.triggerDiscovery")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleTriggerScrape}
              disabled={loadingAction === "scrape"}
              className="border-green-600 bg-green-600/10 text-green-700 hover:bg-green-600/20 dark:text-green-400 dark:hover:bg-green-600/20"
            >
              {loadingAction === "scrape" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              {t("admin.pool.triggerScraping")}
            </Button>
            <Button
              variant="destructive"
              size="sm"
              onClick={handleClearUserProducts}
              disabled={loadingAction === "clear"}
            >
              {loadingAction === "clear" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Scissors className="mr-2 size-4" />
              )}
              {t("admin.pool.clearUserProducts")}
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleCleanupInvalid}
              disabled={loadingAction === "cleanup"}
            >
              {loadingAction === "cleanup" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <RefreshCw className="mr-2 size-4" />
              )}
              Очистить невалидные товары
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleDeduplicate}
              disabled={loadingAction === "deduplicate"}
            >
              {loadingAction === "deduplicate" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Merge className="mr-2 size-4" />
              )}
              Дедупликация маркетплейсов
            </Button>
            <Button
              variant="outline"
              size="sm"
              onClick={handleClearPool}
              disabled={loadingAction === "clearPool"}
              className="border-red-500/50 text-red-600 hover:bg-red-500/10 dark:text-red-400"
            >
              {loadingAction === "clearPool" ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Scissors className="mr-2 size-4" />
              )}
              Очистить пул полностью
            </Button>
          </div>
          {diagnostics && (
            <div className="space-y-3 rounded-lg border bg-muted/30 p-4">
              <p className="text-sm font-medium text-muted-foreground">
                {t("admin.pool.diagnosticsResult")}
              </p>
              <div className="space-y-1 text-sm">
                <p>
                  {t("admin.pool.marketplaces")}:{" "}
                  {diagnostics.marketplaces?.total ?? 0}{" "}
                  ({t("admin.pool.active")}:{" "}
                  {diagnostics.marketplaces?.active ?? 0}, quota=0:{" "}
                  {diagnostics.markplaces?.zero_quota ?? 0})
                </p>
                <p>
                  {t("admin.pool.productsInPool")}:{" "}
                  {diagnostics.global_products?.total ?? 0}
                </p>
                <p>
                  {t("admin.pool.priceSnapshots")}:{" "}
                  {diagnostics.price_snapshots ?? 0}
                </p>
                <p>
                  {t("admin.pool.discoveryLogs")}:{" "}
                  {diagnostics.discovery_logs?.total ?? 0}
                </p>
                {(diagnostics.diagnosis ?? []).length > 0 && (
                  <>
                    <p className="mt-2 font-medium text-amber-600 dark:text-amber-400">
                      ⚠️ {t("admin.pool.problems")}:
                    </p>
                    <ul className="list-inside list-disc space-y-1 text-muted-foreground">
                      {(diagnostics.diagnosis ?? []).map((msg, i) => (
                        <li key={i}>{msg}</li>
                      ))}
                    </ul>
                  </>
                )}
              </div>
              <details className="mt-2">
                <summary className="cursor-pointer text-xs text-muted-foreground hover:underline">
                  {t("admin.pool.showRawJson")}
                </summary>
                <pre className="mt-2 max-h-48 overflow-auto rounded bg-muted/50 p-2 text-xs">
                  {JSON.stringify(diagnostics, null, 2)}
                </pre>
              </details>
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}

const API_STATUS_LABELS: Record<string, string> = {
  forex: "Frankfurter (Forex)",
  crypto: "Binance (Crypto)",
  commodities: "GoldAPI + Alpha Vantage",
  fuel: "Fuel",
  decodo: "Decodo (Scraping)",
  claude: "Claude AI",
  resend: "Resend (Email)",
  telegram: "Telegram Bot",
};

function ApiHealthSection() {
  const { data, isLoading } = useApiHealth();

  if (isLoading || !data) {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Состояние API</CardTitle>
        </CardHeader>
        <CardContent>
          <Skeleton className="h-32 w-full" />
        </CardContent>
      </Card>
    );
  }

  const providers = data.providers ?? {};
  const apiKeys = data.api_keys ?? {};

  const getStatusDot = (key: string, prov: { status?: string } | undefined, cfg: { configured?: boolean } | undefined) => {
    if (["decodo", "claude", "resend", "telegram"].includes(key)) {
      return cfg?.configured ? "🟢" : "⚪";
    }
    if (prov?.status === "success") return "🟢";
    if (prov?.status === "error") return "🔴";
    if (prov?.status === "running") return "🟡";
    return "🟡";
  };

  const getStatusLabel = (key: string, prov: { status?: string; error?: string } | undefined, cfg: { configured?: boolean } | undefined) => {
    if (["decodo", "claude", "resend", "telegram"].includes(key)) {
      return cfg?.configured ? "Настроен" : "Не настроен";
    }
    if (prov?.status === "success") return "Работает";
    if (prov?.status === "error") return prov?.error ?? "Ошибка";
    if (prov?.status === "running") return "Выполняется";
    return "—";
  };

  const rows = [
    "forex",
    "crypto",
    "commodities",
    "fuel",
    "decodo",
    "claude",
    "resend",
    "telegram",
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle>Состояние API</CardTitle>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>API</TableHead>
              <TableHead>Статус</TableHead>
              <TableHead>Обновлено</TableHead>
              <TableHead>Данные</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {rows.map((key) => {
              const prov = providers[key];
              const cfgKey =
                key === "forex"
                  ? "frankfurter"
                  : key === "crypto"
                    ? "binance"
                    : key === "commodities"
                      ? "goldapi"
                      : key;
              const cfg = apiKeys[cfgKey];
              const name = cfg?.name ?? API_STATUS_LABELS[key] ?? key;
              return (
                <TableRow key={key}>
                  <TableCell>
                    {getStatusDot(key, prov, cfg)} {name}
                  </TableCell>
                  <TableCell>{getStatusLabel(key, prov, cfg)}</TableCell>
                  <TableCell>
                    {prov?.last_refresh
                      ? formatRelativeTime(prov.last_refresh, "ru")
                      : "—"}
                  </TableCell>
                  <TableCell>{prov?.items_count ?? "—"}</TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  );
}

function MarketsRefreshCard() {
  const { t, i18n } = useTranslation();
  const ingest = useMarketsIngest();
  const { data: refreshMetadata } = useQuery({
    queryKey: marketsQueryKeys.refreshMetadata(),
    queryFn: async () => {
      const { data } = await marketsApi.getRefreshMetadata();
      return data;
    },
  });

  const lastSuccess = refreshMetadata?.items?.find(
    (i) => i.refresh_type === "forex" || i.refresh_type === "crypto"
  )?.last_successful_refresh;
  const lastError = refreshMetadata?.items?.find(
    (i) => i.refresh_type === "forex" || i.refresh_type === "crypto"
  )?.last_failed_refresh;

  const handleRefresh = async () => {
    try {
      await ingest.mutateAsync();
      toast.success(t("admin.markets.refreshEnqueued"));
    } catch {
      toast.error(t("admin.markets.refreshError"));
    }
  };

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("admin.markets.title")}</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div className="text-sm text-muted-foreground">
            {lastSuccess ? (
              <span>
                {t("admin.markets.lastRefresh")}:{" "}
                {formatRelativeTime(lastSuccess, i18n.language || "en")}
              </span>
            ) : lastError ? (
              <span className="text-destructive">
                {t("admin.markets.lastRefresh")}: {t("admin.claude.error")}
              </span>
            ) : (
              <span>{t("markets.analytics.noData")}</span>
            )}
          </div>
          <Button
            onClick={handleRefresh}
            disabled={ingest.isPending}
            variant="outline"
          >
            {ingest.isPending ? (
              <Loader2 className="size-4 animate-spin" />
            ) : (
              <RefreshCw className="size-4" />
            )}{" "}
            {t("admin.markets.refresh")}
          </Button>
        </div>
      </CardContent>
    </Card>
  );
}

export function AdminPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  const [addUrl, setAddUrl] = useState("");
  const [expandedMarketplace, setExpandedMarketplace] = useState<string | null>(
    null
  );

  const { data: stats, isLoading: statsLoading } = useAdminStats();
  const { data: marketplaces } = useAdminMarketplaces();
  const { data: scrapeActivity } = useScrapeActivity();
  const { data: errorDistribution } = useErrorDistribution();
  const { data: users } = useAdminUsers();

  const addMarketplace = useAddMarketplace();
  const deleteMarketplace = useDeleteMarketplace();

  const handleAddMarketplace = async () => {
    const url = addUrl.trim();
    if (!url) return;
    try {
      await addMarketplace.mutateAsync(url);
      toast.success(t("admin.addMarketplace.success"));
      setAddUrl("");
    } catch (err: unknown) {
      const msg =
        err &&
        typeof err === "object" &&
        "response" in err &&
        err.response &&
        typeof err.response === "object" &&
        "data" in err.response
          ? (err.response.data as { detail?: string }).detail
          : t("common.error");
      toast.error(typeof msg === "string" ? msg : t("common.error"));
    }
  };

  const sortedMarketplaces = [...(marketplaces ?? [])].sort((a, b) => {
    const statusOrder = (s: AdminMarketplaceType) =>
      s.last_scrape_status === "error" ? 0 : s.last_scrape_status ? 1 : 2;
    return statusOrder(a) - statusOrder(b);
  });

  const errorRate = stats?.error_rate_today ?? 0;
  const errorRateColor =
    errorRate < 5
      ? "text-[var(--color-price-down)]"
      : errorRate <= 15
        ? "text-[var(--color-promo)]"
        : "text-[var(--color-price-up)]";

  return (
    <div className="space-y-8">
      <h1 className="font-display text-2xl font-bold tracking-tight">
        {t("admin.title")}
      </h1>

      {/* Stat cards */}
      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-5">
        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <p className="text-sm font-medium text-muted-foreground">
              {t("admin.stats.users")}
            </p>
            <Users className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              <div className="text-2xl font-bold">
                {stats?.users_count ?? stats?.users ?? 0}
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <p className="text-sm font-medium text-muted-foreground">
              {t("admin.stats.marketplaces")}
            </p>
            <Store className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {stats?.marketplaces_count ?? stats?.marketplaces ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t("admin.stats.activeMarketplaces", {
                    count:
                      stats?.active_marketplaces_count ?? stats?.marketplaces ?? 0,
                  })}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <p className="text-sm font-medium text-muted-foreground">
              {t("admin.stats.scrapesToday")}
            </p>
            <Activity className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              <>
                <div className="text-2xl font-bold">
                  {stats?.total_scrapes_today ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {stats?.successful_scrapes_today ?? 0} /{" "}
                  {stats?.failed_scrapes_today ?? 0}
                </p>
              </>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
            <p className="text-sm font-medium text-muted-foreground">
              {t("admin.stats.errors")}
            </p>
            <AlertTriangle className="size-4 text-muted-foreground" />
          </CardHeader>
          <CardContent>
            {statsLoading ? (
              <Skeleton className="h-8 w-12" />
            ) : (
              <div className={`text-2xl font-bold ${errorRateColor}`}>
                {t("admin.stats.errorRate", {
                  rate: errorRate,
                })}
              </div>
            )}
          </CardContent>
        </Card>

        <ClaudeStatusCard />
      </div>

      {/* Add marketplace */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.addMarketplace.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-2">
            <Input
              placeholder={t("admin.addMarketplace.placeholder")}
              value={addUrl}
              onChange={(e) => setAddUrl(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && handleAddMarketplace()}
            />
            <Button
              onClick={handleAddMarketplace}
              disabled={addMarketplace.isPending || !addUrl.trim()}
            >
              {addMarketplace.isPending ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <Plus className="size-4" />
              )}{" "}
              {t("admin.addMarketplace.button")}
            </Button>
          </div>
        </CardContent>
      </Card>

      <MarketsRefreshCard />

      {/* API status */}
      <ApiHealthSection />

      {/* Scrape activity chart */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.scrapeActivity.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {!scrapeActivity ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart
                  data={scrapeActivity.labels.map((l, i) => ({
                    date: l,
                    success: scrapeActivity.datasets[0]?.data.at(i) ?? 0,
                    errors: scrapeActivity.datasets[1]?.data.at(i) ?? 0,
                  }))}
                >
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar dataKey="success" fill="#22c55e" radius={[4, 4, 0, 0]} />
                  <Bar dataKey="errors" fill="#ef4444" radius={[4, 4, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Pool management — after Scrape activity */}
      <PoolManagementCard />

      {/* Error distribution */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.errorDistribution.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          {!errorDistribution ? (
            <Skeleton className="h-64 w-full" />
          ) : (
            <div className="h-64 w-full">
              <ResponsiveContainer width="100%" height="100%">
                <PieChart>
                  <Pie
                    data={errorDistribution.labels.map((l, i) => ({
                      name: l,
                      value: errorDistribution.data.at(i) ?? 0,
                    }))}
                    cx="50%"
                    cy="50%"
                    innerRadius={40}
                    outerRadius={80}
                    paddingAngle={2}
                    dataKey="value"
                    label={({ name, value }) =>
                      value > 0 ? `${name}: ${value}` : ""
                    }
                  >
                    {errorDistribution.labels.map((_, i) => (
                      <Cell
                        key={i}
                        fill={
                          [
                            "#f59e0b",
                            "#ef4444",
                            "#8b5cf6",
                            "#06b6d4",
                            "#6b7280",
                          ][i % 5]
                        }
                      />
                    ))}
                  </Pie>
                </PieChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Marketplaces table */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.marketplaces.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead></TableHead>
                <TableHead>{t("common.name")}</TableHead>
                <TableHead>{t("admin.marketplaces.country")}</TableHead>
                <TableHead>{t("common.status")}</TableHead>
                <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                <TableHead>{t("admin.marketplaces.lastScrape")}</TableHead>
                <TableHead>{t("admin.marketplaces.products")}</TableHead>
                <TableHead>{t("common.actions")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {sortedMarketplaces.map((mp) => (
                <MarketplaceRow
                  key={mp.marketplace_id}
                  mp={mp}
                  expanded={expandedMarketplace === mp.marketplace_id}
                  onToggle={() =>
                    setExpandedMarketplace(
                      expandedMarketplace === mp.marketplace_id
                        ? null
                        : mp.marketplace_id
                    )
                  }
                  onDelete={() => {
                    if (mp.source === "registry") {
                      toast.error(t("admin.marketplaces.cannotDeleteBuiltin"));
                      return;
                    }
                    deleteMarketplace.mutate(mp.marketplace_id);
                  }}
                  t={t}
                  locale={locale}
                />
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>

      {/* Users table */}
      <Card>
        <CardHeader>
          <CardTitle>{t("admin.users.title")}</CardTitle>
        </CardHeader>
        <CardContent>
          <Table>
            <TableHeader>
              <TableRow>
                <TableHead>Email</TableHead>
                <TableHead>{t("common.name")}</TableHead>
                <TableHead>{t("settings.plan")}</TableHead>
                <TableHead>{t("admin.marketplaces.products")}</TableHead>
                <TableHead>{t("admin.users.registration")}</TableHead>
                <TableHead>{t("admin.users.lastLogin")}</TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {(users ?? []).map((u) => (
                <TableRow key={u.id}>
                  <TableCell>{u.email}</TableCell>
                  <TableCell>{u.name ?? u.email?.split("@")[0] ?? "—"}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{u.plan ?? "—"}</Badge>
                  </TableCell>
                  <TableCell>{u.products_count ?? 0}</TableCell>
                  <TableCell>{formatDate(u.created_at, locale)}</TableCell>
                  <TableCell>
                    {u.last_login_at
                      ? formatRelativeTime(u.last_login_at, locale)
                      : "—"}
                  </TableCell>
                </TableRow>
              ))}
            </TableBody>
          </Table>
        </CardContent>
      </Card>
    </div>
  );
}

function formatDate(dateStr: string, locale: string): string {
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(dateStr));
}

function MarketplaceRow({
  mp,
  expanded,
  onToggle,
  onDelete,
  t,
  locale,
}: {
  mp: AdminMarketplaceType;
  expanded: boolean;
  onToggle: () => void;
  onDelete: () => void;
  t: (k: string) => string;
  locale: string;
}) {
  const statusKey =
    mp.last_scrape_status === "success"
      ? "admin.marketplaces.status.success"
      : mp.last_scrape_status === "error"
        ? "admin.marketplaces.status.error"
        : mp.last_scrape_status === "timeout"
          ? "admin.marketplaces.status.timeout"
          : mp.last_scrape_status === "blocked"
            ? "admin.marketplaces.status.blocked"
            : "admin.marketplaces.status.noData";

  const statusVariant =
    mp.last_scrape_status === "success"
      ? "default"
      : mp.last_scrape_status === "error" || mp.last_scrape_status === "blocked"
        ? "destructive"
        : mp.last_scrape_status === "timeout"
          ? "secondary"
          : "outline";

  const progressVariant =
    mp.success_rate >= 95
      ? "default"
      : mp.success_rate >= 80
        ? "warning"
        : "danger";

  return (
    <>
      <TableRow className="cursor-pointer" onClick={onToggle}>
        <TableCell className="w-8">
          {expanded ? (
            <ChevronDown className="size-4" />
          ) : (
            <ChevronRight className="size-4" />
          )}
        </TableCell>
          <TableCell>
            <div>
              <span className="font-medium">{mp.name}</span>
              <span className="ml-1 text-muted-foreground">({mp.domain})</span>
            </div>
          </TableCell>
          <TableCell>
            {getCountryFlag(mp.country)} {mp.country}
          </TableCell>
          <TableCell>
            <Badge variant={statusVariant}>{t(statusKey)}</Badge>
          </TableCell>
          <TableCell>
            <div className="w-24">
              <Progress
                value={mp.success_rate}
                max={100}
                variant={progressVariant}
              />
            </div>
          </TableCell>
          <TableCell>
            {mp.last_scrape_at
              ? formatRelativeTime(mp.last_scrape_at, locale)
              : "—"}
          </TableCell>
          <TableCell>{mp.products_count}</TableCell>
          <TableCell>
            <TooltipRoot>
              <TooltipTrigger asChild>
                <Button
                  variant="ghost"
                  size="icon"
                  onClick={(e) => {
                    e.stopPropagation();
                    onDelete();
                  }}
                  disabled={mp.source === "registry"}
                >
                  <Trash2 className="size-4" />
                </Button>
              </TooltipTrigger>
              <TooltipContent>
                {mp.source === "registry"
                  ? t("admin.marketplaces.cannotDeleteBuiltin")
                  : t("common.delete")}
              </TooltipContent>
            </TooltipRoot>
          </TableCell>
        </TableRow>
      {expanded && (
        <TableRow>
          <TableCell colSpan={8} className="bg-muted/30">
            <MarketplaceLogsPanel marketplaceId={mp.marketplace_id} />
          </TableCell>
        </TableRow>
      )}
    </>
  );
}

function MarketplaceLogsPanel({ marketplaceId }: { marketplaceId: string }) {
  const { data: logs, isLoading } = useMarketplaceLogs(marketplaceId);
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  if (isLoading) return <Skeleton className="h-24 w-full" />;
  if (!logs?.length) return <p className="text-sm text-muted-foreground">{t("common.noData")}</p>;

  return (
    <div className="overflow-x-auto">
      <Table>
        <TableHeader>
          <TableRow>
            <TableHead>URL</TableHead>
            <TableHead>{t("common.status")}</TableHead>
            <TableHead>{t("common.price")}</TableHead>
            <TableHead>ms</TableHead>
            <TableHead>{t("common.date")}</TableHead>
          </TableRow>
        </TableHeader>
        <TableBody>
          {logs.map((log) => (
            <TableRow key={log.id}>
              <TableCell className="max-w-48 truncate">{log.url}</TableCell>
              <TableCell>
                <Badge variant={log.status === "success" ? "default" : "destructive"}>
                  {log.status}
                </Badge>
              </TableCell>
              <TableCell>{log.price_found ?? "—"}</TableCell>
              <TableCell>{log.duration_ms ?? "—"}</TableCell>
              <TableCell>
                {log.created_at
                  ? formatRelativeTime(log.created_at, locale)
                  : "—"}
              </TableCell>
            </TableRow>
          ))}
        </TableBody>
      </Table>
    </div>
  );
}
