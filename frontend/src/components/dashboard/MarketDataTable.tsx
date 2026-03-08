/**
 * Bloomberg-style market data table for dashboard.
 * Data from GET /api/dashboard/market-overview or global market data fallback.
 * Table always shows data (API or global ticker).
 */

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import {
  generateGlobalMarketData,
  sortMarketData,
  type MarketDataItem,
} from "@/data/globalMarketData";
import { formatRelativeTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";

type SortTab = "volatile" | "trending" | "gainers" | "losers" | "recent";

const SORT_MAP: Record<SortTab, string> = {
  volatile: "volatile",
  trending: "trending",
  gainers: "gainers",
  losers: "losers",
  recent: "recent",
};

function formatPrice(price: number, currency: string): string {
  const locale =
    currency === "RUB"
      ? "ru-RU"
      : currency === "EUR"
        ? "de-DE"
        : currency === "KZT"
          ? "kk-KZ"
          : "en-US";
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    maximumFractionDigits: 0,
  }).format(price);
}

function Sparkline({
  data,
  color,
}: {
  data: number[];
  color: string;
}) {
  const validData = data.filter((v) => v > 0);
  if (validData.length < 2) return null;
  const min = Math.min(...validData);
  const max = Math.max(...validData);
  const range = max - min || 1;
  const width = 80;
  const height = 32;
  const points = validData
    .map((v, i) =>
      `${(i / (validData.length - 1)) * width},${height - ((v - min) / range) * height}`
    )
    .join(" ");
  return (
    <svg width={width} height={height} className="inline-block shrink-0">
      <polyline
        points={points}
        fill="none"
        stroke={color}
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function TrendBar({ change1m }: { change1m: number | null }) {
  const pct = change1m ?? 0;
  let gradient = "from-muted to-muted";
  if (pct > 10) gradient = "from-emerald-600 to-emerald-500";
  else if (pct > 5) gradient = "from-emerald-500 to-emerald-400";
  else if (pct > 0) gradient = "from-emerald-400/80 to-emerald-300/80";
  else if (pct > -5) gradient = "from-rose-400/80 to-rose-300/80";
  else if (pct > -10) gradient = "from-rose-500 to-rose-400";
  else gradient = "from-rose-600 to-rose-500";

  const width = Math.min(100, Math.max(0, 50 + pct));
  return (
    <div className="h-2 w-10 overflow-hidden rounded-full bg-muted">
      <div
        className={cn("h-full rounded-full bg-gradient-to-r", gradient)}
        style={{ width: `${width}%` }}
      />
    </div>
  );
}

function ChangeCell({ value }: { value: number | null }) {
  if (value === null) return <span className="text-muted-foreground">—</span>;
  const isPositive = value > 0;
  const isZero = value === 0;
  return (
    <span
      className={cn(
        "font-mono text-sm",
        isZero && "text-muted-foreground",
        isPositive && !isZero && "text-emerald-500 dark:text-emerald-400",
        !isPositive && !isZero && "text-rose-500 dark:text-rose-400"
      )}
    >
      {isPositive ? "+" : ""}
      {value.toFixed(1)}%
    </span>
  );
}

function MarketplaceLogo({
  domain,
  name,
}: {
  domain: string;
  name: string;
}) {
  const [imgError, setImgError] = useState(false);
  const faviconUrl = domain
    ? `https://www.google.com/s2/favicons?domain=${domain}&sz=32`
    : "";
  const fallback = name?.[0]?.toUpperCase() ?? "?";

  if (!faviconUrl || imgError) {
    return (
      <div
        className="flex size-8 shrink-0 items-center justify-center rounded-full bg-primary/20 text-xs font-medium text-primary"
        aria-hidden
      >
        {fallback}
      </div>
    );
  }

  return (
    <div className="relative size-8 shrink-0">
      <img
        src={faviconUrl}
        alt=""
        className="size-8 rounded object-contain"
        onError={() => setImgError(true)}
      />
    </div>
  );
}

export function MarketDataTable() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [activeTab, setActiveTab] = useState<SortTab>("volatile");
  const [displayData, setDisplayData] = useState<MarketDataItem[]>(() =>
    sortMarketData(generateGlobalMarketData(), "volatile")
  );
  const [fading, setFading] = useState(false);

  const { data: apiData, isLoading } = useQuery({
    queryKey: ["dashboard", "market-overview", SORT_MAP[activeTab]],
    queryFn: async () => {
      const { data: res } = await analyticsApi.getMarketOverview(
        SORT_MAP[activeTab],
        50
      );
      return res;
    },
    staleTime: 5 * 60 * 1000,
    retry: false,
  });

  useEffect(() => {
    if (apiData?.items?.length) {
      setDisplayData(
        apiData.items.map((r) => ({
          ...r,
          change_24h: r.change_24h ?? 0,
          change_3d: r.change_3d ?? 0,
          change_1w: r.change_1w ?? 0,
          change_1m: r.change_1m ?? 0,
        }))
      );
    } else {
      setDisplayData(sortMarketData(generateGlobalMarketData(), SORT_MAP[activeTab]));
    }
  }, [apiData, activeTab]);

  useEffect(() => {
    const interval = setInterval(() => {
      if (!apiData?.items?.length) {
        setFading(true);
        setTimeout(() => {
          setDisplayData(sortMarketData(generateGlobalMarketData(), SORT_MAP[activeTab]));
          setFading(false);
        }, 500);
      }
    }, 10 * 60 * 1000);
    return () => clearInterval(interval);
  }, [apiData?.items?.length, activeTab]);

  const items = displayData.length ? displayData : generateGlobalMarketData();
  const total = apiData?.total ?? items.length;
  const lastUpdated = items[0]?.last_updated;
  const relativeTime = lastUpdated
    ? formatRelativeTime(lastUpdated, locale)
    : "";

  const tabs: { key: SortTab; i18nKey: string }[] = [
    { key: "volatile", i18nKey: "dashboard.market.mostVolatile" },
    { key: "trending", i18nKey: "dashboard.market.trendingNow" },
    { key: "gainers", i18nKey: "dashboard.market.topGainers" },
    { key: "losers", i18nKey: "dashboard.market.topLosers" },
    { key: "recent", i18nKey: "dashboard.market.recentlyUpdated" },
  ];

  return (
    <div className="flex min-h-[600px] flex-1 flex-col rounded-xl border border-border bg-card/60 backdrop-blur dark:border-border">
      <h3 className="mb-4 px-4 pt-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("dashboard.market.title")}
      </h3>

      {/* Tabs */}
      <div className="flex flex-wrap gap-1 border-b border-border px-4 dark:border-border">
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "border-primary text-foreground"
                : "border-transparent text-muted-foreground hover:text-foreground"
            )}
          >
            {t(tab.i18nKey)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div
        className={cn(
          "max-h-[500px] flex-1 overflow-y-auto transition-opacity duration-500",
          fading ? "opacity-0" : "opacity-100"
        )}
      >
        <AnimatePresence mode="wait">
          {items.length === 0 ? (
            <motion.div
              key="empty"
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              className="px-4 py-12 text-center text-sm text-muted-foreground"
            >
              {t("dashboard.market.noData")}
            </motion.div>
          ) : (
            <motion.table
              key={activeTab}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.15 }}
              className="w-full min-w-[700px]"
            >
              <thead className="sticky top-0 z-10 bg-card/95 backdrop-blur dark:bg-card/95">
                <tr className="border-b border-border/30 dark:border-border/30">
                  <th className="w-8 px-3 py-2 text-left" />
                  <th className="w-[100px] px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {t("dashboard.market.marketplace")}
                  </th>
                  <th className="min-w-[120px] px-3 py-2 text-left text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {t("dashboard.market.product")}
                  </th>
                  <th className="w-20 px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    {t("dashboard.market.price")}
                  </th>
                  <th className="w-[70px] px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    24h
                  </th>
                  <th className="w-[70px] px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    3d
                  </th>
                  <th className="w-[70px] px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    1w
                  </th>
                  <th className="w-[70px] px-3 py-2 text-right text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    1m
                  </th>
                  <th className="w-20 px-3 py-2 text-center text-xs font-medium uppercase tracking-wider text-muted-foreground">
                    —
                  </th>
                  <th className="w-10 px-3 py-2" />
                </tr>
              </thead>
              <tbody>
                {items.map((row, i) => {
                  const ch24 = row.change_24h ?? 0;
                  const ch1m = row.change_1m ?? 0;
                  const sparkColor =
                    ch1m > 0
                      ? "rgb(16 185 129)"
                      : ch1m < 0
                        ? "rgb(244 63 94)"
                        : "rgb(156 163 175)";
                  const rowBg =
                    ch24 > 5
                      ? "bg-emerald-500/5 dark:bg-emerald-500/5"
                      : ch24 < -5
                        ? "bg-rose-500/5 dark:bg-rose-500/5"
                        : "";

                  return (
                    <motion.tr
                      key={row.id}
                      initial={{ opacity: 0, y: 4 }}
                      animate={{ opacity: 1, y: 0 }}
                      transition={{ delay: Math.min(i * 0.02, 0.2) }}
                      className={cn(
                        "h-11 border-b border-border/30 transition-colors hover:bg-accent/10 dark:border-border/30",
                        rowBg
                      )}
                    >
                      <td className="px-3 py-2">
                        <MarketplaceLogo
                          domain={row.marketplace_domain}
                          name={row.marketplace}
                        />
                      </td>
                      <td className="px-3 py-2 text-xs text-muted-foreground">
                        {row.marketplace}
                      </td>
                      <td className="max-w-[200px] px-3 py-2">
                        <Tooltip>
                          <TooltipTrigger asChild>
                            <span className="block truncate text-sm">
                              {row.product_name}
                            </span>
                          </TooltipTrigger>
                          <TooltipContent>
                            <p className="max-w-xs">{row.product_name}</p>
                          </TooltipContent>
                        </Tooltip>
                      </td>
                      <td className="px-3 py-2 text-right font-mono text-sm font-medium">
                        {formatPrice(row.price, row.currency)}
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ChangeCell value={row.change_24h} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ChangeCell value={row.change_3d} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ChangeCell value={row.change_1w} />
                      </td>
                      <td className="px-3 py-2 text-right">
                        <ChangeCell value={row.change_1m} />
                      </td>
                      <td className="px-3 py-2">
                        <div className="flex justify-center">
                          <Sparkline data={row.sparkline_data} color={sparkColor} />
                        </div>
                      </td>
                      <td className="px-3 py-2">
                        <TrendBar change1m={row.change_1m} />
                      </td>
                    </motion.tr>
                  );
                })}
              </tbody>
            </motion.table>
          )}
        </AnimatePresence>
      </div>

      {items.length > 0 && (
        <div className="border-t border-border/30 px-4 py-2 text-xs text-muted-foreground dark:border-border/30">
          {t("dashboard.market.showing", {
            count: items.length,
            total,
          })}
          {relativeTime && (
            <>
              {" • "}
              {t("dashboard.market.updated", { time: relativeTime })}
            </>
          )}
        </div>
      )}
    </div>
  );
}
