/**
 * Market Overview widget for Markets page.
 * Uses markets API only. Client-side sorting by tab. Fade on update.
 */

import { useState, useMemo, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { motion, AnimatePresence } from "framer-motion";
import { keepPreviousData } from "@tanstack/react-query";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";
import { Skeleton } from "@/components/ui/skeleton";
import { useQuery } from "@tanstack/react-query";
import { Database } from "lucide-react";
import { marketsApi, marketsQueryKeys, type MarketsOverviewItem } from "@/api/markets";
import { formatRelativeTime } from "@/lib/formatters";
import { safeFixed, safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

function stringToColor(str: string): string {
  let hash = 0;
  for (let i = 0; i < str.length; i++) hash = str.charCodeAt(i) + ((hash << 5) - hash);
  const h = Math.abs(hash) % 360;
  return `hsl(${h}, 55%, 45%)`;
}

type SortTab = "volatile" | "trending" | "gainers" | "losers" | "recent";

function getSortKey(tab: SortTab): string {
  switch (tab) {
    case "volatile":
      return "volatile";
    case "trending":
      return "trending";
    case "gainers":
      return "gainers";
    case "losers":
      return "losers";
    case "recent":
      return "recent";
  }
}

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
  }).format(safeNumber(price));
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
  const width = Math.min(100, Math.max(0, 50 + pct));
  const isPositive = pct > 0;
  const gradient = isPositive
    ? "linear-gradient(90deg, var(--color-price-down), var(--color-price-down))"
    : "linear-gradient(90deg, var(--color-price-up), var(--color-price-up))";

  return (
    <div
      className="h-2 w-10 overflow-hidden rounded-full"
      style={{ background: "var(--glass-bg)" }}
    >
      <div
        className="h-full rounded-full"
        style={{ width: `${width}%`, background: gradient }}
      />
    </div>
  );
}

function ChangeCell({ value }: { value: number | null }) {
  if (value === null)
    return <span style={{ color: "var(--foreground-muted)" }}>—</span>;
  const isPositive = value > 0;
  const isZero = value === 0;
  return (
    <span
      className="font-mono text-sm"
      style={{
        color: isZero
          ? "var(--foreground-muted)"
          : isPositive
            ? "var(--color-price-down)"
            : "var(--color-price-up)",
      }}
    >
      {isPositive ? "+" : ""}
      {safeFixed(value, 1)}%
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
        className="flex size-8 shrink-0 items-center justify-center rounded-full text-xs font-medium"
        style={{
          background: "var(--accent-bg)",
          color: "var(--accent)",
        }}
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

function ProductThumbnailPlaceholder({ productName }: { productName: string }) {
  const letter = productName?.charAt(0)?.toUpperCase() ?? "?";
  const bg = stringToColor(productName ?? "");
  return (
    <div
      className="flex size-7 shrink-0 items-center justify-center rounded-full text-xs font-bold text-white"
      style={{ backgroundColor: bg }}
      aria-hidden
    >
      {letter}
    </div>
  );
}

export function MarketDataTable() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const [activeTab, setActiveTab] = useState<SortTab>("volatile");
  const [fading, setFading] = useState(false);
  const prevDataRef = useRef<MarketsOverviewItem[]>([]);

  const { data: apiData, isLoading } = useQuery({
    queryKey: marketsQueryKeys.overview("volatile", 50),
    queryFn: async () => {
      const { data } = await marketsApi.getOverview("volatile", 50);
      return data;
    },
    staleTime: 10 * 60 * 1000,
    refetchInterval: 10 * 60 * 1000,
    retry: false,
    placeholderData: keepPreviousData,
  });

  const displayData = apiData?.items ?? [];

  const sortedData = useMemo(() => {
    const sorted = [...displayData];
    switch (activeTab) {
      case "volatile":
        return sorted.sort(
          (a, b) =>
            Math.max(Math.abs(b.change_24h ?? 0), Math.abs(b.change_3d ?? 0)) -
            Math.max(Math.abs(a.change_24h ?? 0), Math.abs(a.change_3d ?? 0))
        );
      case "trending":
        return sorted.sort((a, b) => Math.abs(b.change_24h ?? 0) - Math.abs(a.change_24h ?? 0));
      case "gainers":
        return sorted
          .filter((i) => (i.change_24h ?? 0) > 0)
          .sort((a, b) => (b.change_24h ?? 0) - (a.change_24h ?? 0));
      case "losers":
        return sorted
          .filter((i) => (i.change_24h ?? 0) < 0)
          .sort((a, b) => (a.change_24h ?? 0) - (b.change_24h ?? 0));
      case "recent":
        return sorted.sort(
          (a, b) => new Date(b.last_updated).getTime() - new Date(a.last_updated).getTime()
        );
      default:
        return sorted;
    }
  }, [displayData, activeTab]);

  useEffect(() => {
    if (prevDataRef.current !== displayData) {
      setFading(true);
      const timer = setTimeout(() => {
        setFading(false);
        prevDataRef.current = displayData;
      }, 400);
      return () => clearTimeout(timer);
    }
  }, [displayData]);

  const items = sortedData;
  const total = displayData.length;
  const lastUpdated = displayData[0]?.last_updated;
  const relativeTime = lastUpdated ? formatRelativeTime(lastUpdated, locale) : "";

  const tabs: { key: SortTab; i18nKey: string }[] = [
    { key: "volatile", i18nKey: "dashboard.market.mostVolatile" },
    { key: "trending", i18nKey: "dashboard.market.trendingNow" },
    { key: "gainers", i18nKey: "dashboard.market.topGainers" },
    { key: "losers", i18nKey: "dashboard.market.topLosers" },
    { key: "recent", i18nKey: "dashboard.market.recentlyUpdated" },
  ];

  return (
    <div className="glass-card flex min-h-[600px] flex-1 flex-col overflow-hidden rounded-xl">
      <h3
        className="mb-4 px-4 pt-4 text-sm font-semibold uppercase tracking-wider"
        style={{
          background:
            "linear-gradient(135deg, var(--foreground), var(--foreground-muted))",
          WebkitBackgroundClip: "text",
          WebkitTextFillColor: "transparent",
          backgroundClip: "text",
          fontFamily: "var(--font-display)",
        }}
      >
        {t("market.overview.title")}
      </h3>

      {/* Tabs */}
      <div
        className="flex flex-wrap gap-1 border-b px-4"
        style={{ borderColor: "var(--glass-border)" }}
      >
        {tabs.map((tab) => (
          <button
            key={tab.key}
            type="button"
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              "border-b-2 px-3 py-2 text-sm font-medium transition-colors",
              activeTab === tab.key
                ? "text-[var(--foreground)]"
                : "text-[var(--foreground-muted)] hover:text-[var(--foreground)]"
            )}
            style={
              activeTab === tab.key
                ? { borderColor: "var(--accent)" }
                : { borderColor: "transparent" }
            }
          >
            {t(tab.i18nKey)}
          </button>
        ))}
      </div>

      {/* Table */}
      <div className="max-h-[500px] flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="space-y-3 px-4 py-8">
            {Array.from({ length: 5 }).map((_, i) => (
              <Skeleton key={i} className="h-11 w-full" />
            ))}
          </div>
        ) : (
          <AnimatePresence mode="wait">
            {items.length === 0 ? (
              <motion.div
                key="empty"
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                className="flex flex-col items-center justify-center px-4 py-16 text-center"
                style={{ color: "var(--foreground-muted)" }}
              >
                {displayData.length === 0 ? (
                  <>
                    <Database className="mb-4 size-12 opacity-50" />
                    <p className="mb-1 text-sm font-medium">{t("market.overview.noData")}</p>
                    <p className="max-w-sm text-xs">
                      {t("market.overview.noDataDescription")}
                    </p>
                  </>
                ) : (
                  <p className="text-sm font-medium">{t("market.overview.noItems")}</p>
                )}
              </motion.div>
            ) : (
              <div className={cn("transition-opacity duration-400", fading ? "opacity-30" : "opacity-100")}>
              <motion.table
                key={activeTab}
                initial={{ opacity: 0 }}
                animate={{ opacity: 1 }}
                exit={{ opacity: 0 }}
                transition={{ duration: 0.15 }}
                className="w-full min-w-[700px]"
              >
                <thead
                  className="sticky top-0 z-10 backdrop-blur"
                  style={{
                    background: "var(--background-elevated-subtle)",
                  }}
                >
                  <tr style={{ borderBottom: "1px solid var(--border)" }}>
                    <th className="w-8 px-2 pl-4 py-2" />
                    <th
                      className="w-[100px] pl-4 py-2 text-left text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      {t("dashboard.market.marketplace")}
                    </th>
                    <th className="w-10 px-2 py-2" style={{ width: 40 }} />
                    <th
                      className="min-w-[120px] px-2 py-2 text-left text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      {t("dashboard.market.product")}
                    </th>
                    <th
                      className="w-20 px-2 py-2 text-right text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      {t("dashboard.market.price")}
                    </th>
                    <th
                      className="w-[70px] px-2 py-2 text-right text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      24h
                    </th>
                    <th
                      className="w-[70px] px-2 py-2 text-right text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      3d
                    </th>
                    <th
                      className="w-[70px] px-2 py-2 text-right text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      1w
                    </th>
                    <th
                      className="w-[70px] px-2 py-2 text-right text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      1m
                    </th>
                    <th
                      className="w-20 px-2 py-2 text-center text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      {t("market.overview.thirtyDayChart")}
                    </th>
                    <th
                      className="w-20 px-2 py-2 text-center text-xs font-medium uppercase tracking-wider"
                      style={{ color: "var(--foreground-muted)" }}
                    >
                      {t("market.overview.trend")}
                    </th>
                  </tr>
                </thead>
                <tbody>
                  {items.map((row, i) => {
                    const ch24 = row.change_24h ?? 0;
                    const ch1m = row.change_1m ?? 0;
                    const sparkColor =
                      ch1m > 0
                        ? "var(--color-price-down)"
                        : ch1m < 0
                          ? "var(--color-price-up)"
                          : "var(--foreground-muted)";
                    const rowBg =
                      ch24 > 5
                        ? "var(--row-tint-green)"
                        : ch24 < -5
                          ? "var(--row-tint-red)"
                          : "transparent";

                    return (
                      <motion.tr
                        key={row.id}
                        initial={{ opacity: 0, y: 4 }}
                        animate={{ opacity: 1, y: 0 }}
                        transition={{ delay: Math.min(i * 0.02, 0.2) }}
                        className="h-11 transition-colors hover:bg-[var(--glass-bg-hover)]"
                        style={{
                          borderBottom: "1px solid var(--border)",
                          background: rowBg,
                        }}
                      >
                        <td className="px-2 pl-4 py-2">
                          <MarketplaceLogo
                            domain={row.marketplace_domain}
                            name={row.marketplace}
                          />
                        </td>
                        <td
                          className="pl-4 py-2 text-left text-xs"
                          style={{ color: "var(--foreground-muted)" }}
                        >
                          {row.marketplace}
                        </td>
                        <td className="w-10 px-2 py-2" style={{ width: 40 }}>
                          <ProductThumbnailPlaceholder productName={row.product_name} />
                        </td>
                        <td className="max-w-[200px] px-2 py-2">
                          <Tooltip>
                            <TooltipTrigger asChild>
                              <span className="block truncate text-sm">
                                {row.product_name}
                              </span>
                            </TooltipTrigger>
                            <TooltipContent className="glass-card border-[var(--glass-border)]">
                              <p className="max-w-xs">{row.product_name}</p>
                            </TooltipContent>
                          </Tooltip>
                        </td>
                        <td className="px-2 py-2 text-right font-mono text-sm font-medium">
                          {formatPrice(row.price, row.currency)}
                        </td>
                        <td className="px-2 py-2 text-right">
                          <ChangeCell value={row.change_24h} />
                        </td>
                        <td className="px-2 py-2 text-right">
                          <ChangeCell value={row.change_3d} />
                        </td>
                        <td className="px-2 py-2 text-right">
                          <ChangeCell value={row.change_1w} />
                        </td>
                        <td className="px-2 py-2 text-right">
                          <ChangeCell value={row.change_1m} />
                        </td>
                        <td className="px-2 py-2">
                          <div className="flex justify-center">
                            <Sparkline
                              data={row.sparkline_data ?? []}
                              color={sparkColor}
                            />
                          </div>
                        </td>
                        <td className="px-2 py-2">
                          <div className="flex justify-center">
                            <TrendBar change1m={row.change_1m} />
                          </div>
                        </td>
                      </motion.tr>
                    );
                  })}
                </tbody>
              </motion.table>
              </div>
            )}
          </AnimatePresence>
        )}
      </div>

      {items.length > 0 && (
        <div
          className="border-t px-4 py-2 text-xs"
          style={{
            borderColor: "var(--border)",
            color: "var(--foreground-muted)",
          }}
        >
          {t("market.overview.showing", {
            count: items.length,
            total,
            time: relativeTime,
          })}
        </div>
      )}
    </div>
  );
}
