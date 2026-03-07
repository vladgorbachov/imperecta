// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Administration page for superusers.
 * Stats, Claude API status, add marketplace, scrape activity, error distribution,
 * marketplace table, users table.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
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
} from "@/hooks/useAdmin";
import { formatRelativeTime } from "@/lib/formatters";
import type { AdminMarketplace as AdminMarketplaceType } from "@/api/admin";

const COUNTRY_FLAGS: Record<string, string> = {
  RU: "🇷🇺",
  KZ: "🇰🇿",
  BY: "🇧🇾",
  UA: "🇺🇦",
  DE: "🇩🇪",
  PL: "🇵🇱",
  XX: "🌐",
};

function getCountryFlag(country: string): string {
  return COUNTRY_FLAGS[country] ?? country;
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

  const { health, stats } = data;
  const status = health.status;

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
          ? "bg-amber-500"
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
          {t("admin.claude.latency", { ms: health.latency_ms })}
        </p>
        {expanded && (
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

  const errorRateColor =
    stats && stats.error_rate_today < 5
      ? "text-green-600 dark:text-green-400"
      : stats && stats.error_rate_today <= 15
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";

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
              <div className="text-2xl font-bold">{stats?.users_count ?? 0}</div>
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
                  {stats?.marketplaces_count ?? 0}
                </div>
                <p className="text-xs text-muted-foreground">
                  {t("admin.stats.activeMarketplaces", {
                    count: stats?.active_marketplaces_count ?? 0,
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
                  rate: stats?.error_rate_today ?? 0,
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
                <BarChart data={scrapeActivity.labels.map((l, i) => ({
                  date: l,
                  [scrapeActivity.datasets[0]?.label ?? "Успешно"]:
                    scrapeActivity.datasets[0]?.data[i] ?? 0,
                  [scrapeActivity.datasets[1]?.label ?? "Ошибки"]:
                    scrapeActivity.datasets[1]?.data[i] ?? 0,
                }))}>
                  <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                  <XAxis dataKey="date" tick={{ fontSize: 12 }} />
                  <YAxis tick={{ fontSize: 12 }} />
                  <Tooltip />
                  <Legend />
                  <Bar
                    dataKey={scrapeActivity.datasets[0]?.label ?? "Успешно"}
                    fill="#22c55e"
                    radius={[4, 4, 0, 0]}
                  />
                  <Bar
                    dataKey={scrapeActivity.datasets[1]?.label ?? "Ошибки"}
                    fill="#ef4444"
                    radius={[4, 4, 0, 0]}
                  />
                </BarChart>
              </ResponsiveContainer>
            </div>
          )}
        </CardContent>
      </Card>

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
                      value: errorDistribution.data[i] ?? 0,
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
                  <TableCell>{u.name}</TableCell>
                  <TableCell>
                    <Badge variant="secondary">{u.plan}</Badge>
                  </TableCell>
                  <TableCell>{u.products_count}</TableCell>
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
