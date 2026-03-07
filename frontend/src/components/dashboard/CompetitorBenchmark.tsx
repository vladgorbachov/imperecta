/**
 * Competitor benchmark: table or grid view.
 * Data: GET /api/analytics/competitor-benchmark
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutGrid, List } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type ViewMode = "table" | "grid";

function toMarketplaceDisplay(m: string): string {
  const map: Record<string, string> = {
    ozon: "Ozon",
    wildberries: "Wildberries",
    kaspi: "Kaspi",
    custom: "Custom",
  };
  return map[m?.toLowerCase() ?? ""] ?? m;
}

function getBarColor(index: number): string {
  if (index <= 40) return "bg-price-down";
  if (index <= 70) return "bg-amber-500";
  return "bg-price-up";
}

export function CompetitorBenchmark() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>("table");

  const { data: benchmarksRaw, isLoading } = useQuery({
    queryKey: ["analytics", "competitor-benchmark"],
    queryFn: () => analyticsApi.getCompetitorBenchmark().then((r) => r.data),
  });

  const benchmarks = (benchmarksRaw ?? []).map((b) => ({
    id: (b as { competitor_id?: string }).competitor_id ?? (b as { id?: string }).id ?? "",
    name: (b as { competitor_name?: string }).competitor_name ?? (b as { name?: string }).name ?? "",
    marketplace: toMarketplaceDisplay(
      (b as { marketplace?: string }).marketplace ?? ""
    ),
    priceIndex: (b as { price_index?: number }).price_index ?? (b as { priceIndex?: number }).priceIndex ?? 100,
    lastChange: (b as { last_change_pct?: number }).last_change_pct ?? (b as { lastChange?: number }).lastChange ?? 0,
    aggressiveness: ((b as { aggressiveness?: string }).aggressiveness ?? "passive") as
      | "aggressive"
      | "moderate"
      | "passive",
  }));

  if (isLoading) {
    return (
      <div className="rounded-xl border border-border bg-card p-4 shadow-sm dark:border-border">
        <Skeleton className="mb-4 h-6 w-48" />
        <div className="space-y-2">
          {[0, 1, 2, 3].map((i) => (
            <Skeleton key={i} className="h-20 w-full" />
          ))}
        </div>
      </div>
    );
  }

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.3 }}
      className="rounded-xl border border-border bg-card p-4 shadow-sm dark:border-border"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3 className="text-sm font-semibold uppercase tracking-wider text-muted-foreground">
          {t("dashboard.benchmark.title")}
        </h3>
        <div className="flex gap-1">
          <Button
            variant={viewMode === "table" ? "default" : "ghost"}
            size="icon"
            className="size-8"
            onClick={() => setViewMode("table")}
            aria-label="Table view"
          >
            <List className="size-4" />
          </Button>
          <Button
            variant={viewMode === "grid" ? "default" : "ghost"}
            size="icon"
            className="size-8"
            onClick={() => setViewMode("grid")}
            aria-label="Grid view"
          >
            <LayoutGrid className="size-4" />
          </Button>
        </div>
      </div>

      {benchmarks.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("dashboard.benchmark.noData")}
        </p>
      ) : viewMode === "table" ? (
        <div className="space-y-2">
          {benchmarks.map((b) => (
            <div
              key={b.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border bg-muted/30 p-3 dark:border-border"
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium">{b.name}</p>
                <Badge variant="secondary" className="mt-1 text-xs">
                  {b.marketplace}
                </Badge>
              </div>
              <div className="w-24">
                <div className="h-2 overflow-hidden rounded-full bg-muted">
                  <div
                    className={cn("h-full rounded-full transition-all", getBarColor(b.priceIndex))}
                    style={{ width: `${b.priceIndex}%` }}
                  />
                </div>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  {b.priceIndex} {t("dashboard.benchmark.priceIndex")}
                </p>
              </div>
              <p
                className={cn(
                  "text-sm font-medium",
                  b.lastChange >= 0 ? "text-price-up" : "text-price-down"
                )}
              >
                {b.lastChange >= 0 ? "+" : ""}
                {b.lastChange.toFixed(1)}%
              </p>
              <Badge variant="outline" className="text-xs">
                {t(`dashboard.benchmark.${b.aggressiveness}`)}
              </Badge>
              <Button variant="ghost" size="sm" onClick={() => navigate("/competitors")}>
                {t("dashboard.benchmark.details")}
              </Button>
            </div>
          ))}
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
          {benchmarks.map((b) => (
            <div
              key={b.id}
              className="rounded-lg border border-border bg-muted/30 p-3 dark:border-border"
            >
              <p className="font-medium">{b.name}</p>
              <Badge variant="secondary" className="mt-1 text-xs">
                {b.marketplace}
              </Badge>
              <div className="mt-2 h-2 overflow-hidden rounded-full bg-muted">
                <div
                  className={cn("h-full rounded-full", getBarColor(b.priceIndex))}
                  style={{ width: `${b.priceIndex}%` }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span
                  className={cn(
                    "text-sm",
                    b.lastChange >= 0 ? "text-price-up" : "text-price-down"
                  )}
                >
                  {b.lastChange >= 0 ? "+" : ""}
                  {b.lastChange.toFixed(1)}%
                </span>
                <Button variant="ghost" size="sm" onClick={() => navigate("/competitors")}>
                  {t("dashboard.benchmark.details")}
                </Button>
              </div>
            </div>
          ))}
        </div>
      )}
    </motion.div>
  );
}
