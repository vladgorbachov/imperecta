/**
 * Competitor benchmark: table or grid view.
 * TODO: create GET /api/analytics/competitor-benchmark. Mock 5 competitors.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import { LayoutGrid, List } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { cn } from "@/lib/utils";

// TODO: create GET /api/analytics/competitor-benchmark
const MOCK_BENCHMARKS = [
  {
    id: "1",
    name: "Ozon Seller",
    marketplace: "Ozon" as const,
    priceIndex: 72,
    lastChange: 3.2,
    aggressiveness: "aggressive" as const,
  },
  {
    id: "2",
    name: "WB Premium",
    marketplace: "Wildberries" as const,
    priceIndex: 45,
    lastChange: -1.5,
    aggressiveness: "moderate" as const,
  },
  {
    id: "3",
    name: "Kaspi Partner",
    marketplace: "Kaspi" as const,
    priceIndex: 38,
    lastChange: 0.8,
    aggressiveness: "passive" as const,
  },
  {
    id: "4",
    name: "MegaStore",
    marketplace: "Ozon" as const,
    priceIndex: 88,
    lastChange: 5.1,
    aggressiveness: "aggressive" as const,
  },
  {
    id: "5",
    name: "TechDeal",
    marketplace: "Wildberries" as const,
    priceIndex: 55,
    lastChange: -2.3,
    aggressiveness: "moderate" as const,
  },
];

type ViewMode = "table" | "grid";

function getBarColor(index: number): string {
  if (index <= 40) return "bg-price-down";
  if (index <= 70) return "bg-amber-500";
  return "bg-price-up";
}

export function CompetitorBenchmark() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [viewMode, setViewMode] = useState<ViewMode>("table");

  const benchmarks = MOCK_BENCHMARKS;

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.2, duration: 0.3 }}
      className="rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg dark:bg-zinc-900/60 dark:border-border/50"
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

      {viewMode === "table" ? (
        <div className="space-y-2">
          {benchmarks.map((b) => (
            <div
              key={b.id}
              className="flex flex-wrap items-center gap-3 rounded-lg border border-border/50 p-3 dark:border-border/50"
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
              className="rounded-lg border border-border/50 p-3 dark:border-border/50"
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
