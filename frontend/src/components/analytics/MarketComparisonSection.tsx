/**
 * Extended ComparisonMatrix (inline) + Category × Marketplace heatmap.
 * TODO: GET /api/analytics/market-comparison
 */

import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

const CATEGORIES = ["Electronics", "Appliances", "Gadgets", "Accessories"];
const MARKETPLACES = ["Ozon", "WB", "Kaspi"];

interface MarketComparisonSectionProps {
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
}

/** Mock comparison matrix. */
function mockMatrix(
  products: { id: string; name: string }[],
  competitors: { id: string; name: string }[]
): Record<string, Record<string, number>> {
  const cells: Record<string, Record<string, number>> = {};
  const basePrice = 45000;
  products.forEach((p, pi) => {
    cells[p.id] = {};
    competitors.forEach((c, ci) => {
      const myP = basePrice + pi * 2000 + (p.id.charCodeAt(0) % 500);
      const compP = myP * (0.9 + ci * 0.05 + (c.id.charCodeAt(0) % 10) / 100);
      cells[p.id][c.id] = ((myP - compP) / compP) * 100;
    });
  });
  return cells;
}

/** Mock category × marketplace heatmap (price index 0–100). */
function mockCategoryMarketplaceHeatmap(): Record<string, Record<string, number>> {
  const heat: Record<string, Record<string, number>> = {};
  CATEGORIES.forEach((cat, ci) => {
    heat[cat] = {};
    MARKETPLACES.forEach((mp, mi) => {
      heat[cat][mp] = 50 + (ci * 8) + (mi * 5) + ((cat.length + mp.length) % 15);
    });
  });
  return heat;
}

export function MarketComparisonSection({
  products,
  competitors,
}: MarketComparisonSectionProps) {
  const { t } = useTranslation();

  const matrixCells = useMemo(
    () => mockMatrix(products, competitors),
    [products, competitors]
  );
  const heatmapData = useMemo(() => mockCategoryMarketplaceHeatmap(), []);

  const getCellColor = (diffPercent: number) => {
    if (diffPercent <= -10) return "bg-emerald-500/80 dark:bg-emerald-600/80";
    if (diffPercent <= -5) return "bg-emerald-400/60 dark:bg-emerald-500/60";
    if (diffPercent <= 0) return "bg-emerald-300/40 dark:bg-emerald-400/40";
    if (diffPercent <= 5) return "bg-amber-300/40 dark:bg-amber-400/40";
    if (diffPercent <= 10) return "bg-amber-400/60 dark:bg-amber-500/60";
    return "bg-red-500/80 dark:bg-red-600/80";
  };

  const getHeatmapColor = (value: number) => {
    if (value >= 80) return "bg-red-500/70 dark:bg-red-600/70";
    if (value >= 60) return "bg-amber-500/60 dark:bg-amber-500/60";
    if (value >= 40) return "bg-yellow-400/50 dark:bg-yellow-500/50";
    return "bg-emerald-400/50 dark:bg-emerald-500/50";
  };

  const handleExportPdf = () => {
    // TODO: GET /api/analytics/market-comparison + PDF generation
    window.print();
  };

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{t("analytics.comparisonMatrix")}</h3>
        <Button variant="outline" size="sm" onClick={handleExportPdf}>
          {t("analytics.exportPdf")}
        </Button>
      </div>

      {products.length > 0 && competitors.length > 0 ? (
        <div className="overflow-x-auto rounded-lg border border-border dark:border-border">
          <div
            className="grid gap-px bg-border dark:bg-border"
            style={{
              gridTemplateColumns: `minmax(120px,1fr) repeat(${competitors.length}, minmax(80px,1fr))`,
            }}
          >
            <div className="bg-muted/50 p-2 text-xs font-medium dark:bg-muted/30" />
            {competitors.map((c) => (
              <div
                key={c.id}
                className="truncate bg-muted/50 p-2 text-center text-xs font-medium dark:bg-muted/30"
                title={c.name}
              >
                {c.name}
              </div>
            ))}
            {products.flatMap((p) => [
              <div
                key={`label-${p.id}`}
                className="truncate bg-muted/30 p-2 text-xs dark:bg-muted/20"
                title={p.name}
              >
                {p.name}
              </div>,
              ...competitors.map((c) => {
                const diff = matrixCells[p.id]?.[c.id];
                if (diff == null) return <div key={`${p.id}-${c.id}`} className="bg-background p-1" />;
                return (
                  <div
                    key={`${p.id}-${c.id}`}
                    className={cn(
                      "flex min-h-[44px] cursor-default items-center justify-center p-1 text-xs transition-colors hover:ring-2 hover:ring-ring",
                      getCellColor(diff)
                    )}
                  >
                    {diff > 0 ? "+" : ""}{diff.toFixed(0)}%
                  </div>
                );
              }),
            ])}
          </div>
        </div>
      ) : (
        <p className="py-8 text-center text-sm text-muted-foreground">
          {t("competitors.comparisonMatrixEmpty")}
        </p>
      )}

      <div>
        <h3 className="mb-4 text-lg font-semibold">
          {t("analytics.categoryMarketplaceHeatmap")}
        </h3>
        <p className="mb-4 text-sm text-muted-foreground">
          {t("analytics.categoryMarketplaceHint")}
        </p>
        <div
          className="grid gap-px bg-border dark:bg-border"
          style={{
            gridTemplateColumns: `minmax(100px,1fr) repeat(${MARKETPLACES.length}, minmax(80px,1fr))`,
          }}
        >
          <div className="bg-muted/50 p-2 text-xs font-medium dark:bg-muted/30" />
          {MARKETPLACES.map((mp) => (
            <div
              key={mp}
              className="bg-muted/50 p-2 text-center text-xs font-medium dark:bg-muted/30"
            >
              {mp}
            </div>
          ))}
          {CATEGORIES.map((cat) => [
            <div
              key={`row-${cat}`}
              className="truncate bg-muted/30 p-2 text-xs dark:bg-muted/20"
            >
              {cat}
            </div>,
            ...MARKETPLACES.map((mp) => {
              const val = heatmapData[cat]?.[mp] ?? 50;
              return (
                <div
                  key={`${cat}-${mp}`}
                  className={cn(
                    "flex min-h-[48px] items-center justify-center p-2 text-sm font-medium",
                    getHeatmapColor(val)
                  )}
                  title={`${cat} × ${mp}: ${val}`}
                >
                  {val}
                </div>
              );
            }),
          ])}
        </div>
      </div>
    </div>
  );
}
