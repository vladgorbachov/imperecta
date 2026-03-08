/**
 * Competitor benchmark: table or grid view.
 * Glass-card container, gradient title.
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
  if (index <= 40) return "var(--color-price-down)";
  if (index <= 70) return "var(--color-promo)";
  return "var(--color-price-up)";
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
      <div className="glass-card rounded-xl p-4">
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
      className="glass-card rounded-xl p-4"
    >
      <div className="mb-4 flex items-center justify-between">
        <h3
          className="text-sm font-semibold uppercase tracking-wider"
          style={{
            background: "linear-gradient(135deg, var(--foreground), var(--foreground-muted))",
            WebkitBackgroundClip: "text",
            WebkitTextFillColor: "transparent",
            backgroundClip: "text",
            fontFamily: "var(--font-display)",
          }}
        >
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
        <p className="py-6 text-center text-sm" style={{ color: "var(--foreground-muted)" }}>
          {t("dashboard.benchmark.noData")}
        </p>
      ) : viewMode === "table" ? (
        <div className="space-y-2">
          {benchmarks.map((b) => (
            <div
              key={b.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border p-3"
              style={{
                borderColor: "var(--glass-border)",
                background: "var(--glass-bg)",
              }}
            >
              <div className="min-w-0 flex-1">
                <p className="font-medium">{b.name}</p>
                <Badge variant="secondary" className="mt-1 text-xs">
                  {b.marketplace}
                </Badge>
              </div>
              <div className="w-24">
                <div
                  className="h-2 overflow-hidden rounded-full"
                  style={{ background: "var(--glass-bg)" }}
                >
                  <div
                    className="h-full rounded-full transition-all"
                    style={{
                      width: `${b.priceIndex}%`,
                      background: getBarColor(b.priceIndex),
                    }}
                  />
                </div>
                <p className="mt-0.5 text-xs" style={{ color: "var(--foreground-muted)" }}>
                  {b.priceIndex} {t("dashboard.benchmark.priceIndex")}
                </p>
              </div>
              <p
                className="text-sm font-medium"
                style={{
                  color: b.lastChange >= 0 ? "var(--color-price-up)" : "var(--color-price-down)",
                }}
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
              className="rounded-lg border p-3"
              style={{
                borderColor: "var(--glass-border)",
                background: "var(--glass-bg)",
              }}
            >
              <p className="font-medium">{b.name}</p>
              <Badge variant="secondary" className="mt-1 text-xs">
                {b.marketplace}
              </Badge>
              <div
                className="mt-2 h-2 overflow-hidden rounded-full"
                style={{ background: "var(--glass-bg)" }}
              >
                <div
                  className="h-full rounded-full"
                  style={{
                    width: `${b.priceIndex}%`,
                    background: getBarColor(b.priceIndex),
                  }}
                />
              </div>
              <div className="mt-2 flex items-center justify-between">
                <span
                  className="text-sm font-medium"
                  style={{
                    color: b.lastChange >= 0 ? "var(--color-price-up)" : "var(--color-price-down)",
                  }}
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
