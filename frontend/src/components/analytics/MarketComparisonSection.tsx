/**
 * Comparison matrix: products × competitors (% diff).
 * Data: GET /api/analytics/comparison-matrix
 */

import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface MarketComparisonSectionProps {
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
}

function toMarketplaceDisplay(m: string): string {
  const map: Record<string, string> = {
    ozon: "Ozon",
    wildberries: "Wildberries",
    kaspi: "Kaspi",
    custom: "Custom",
  };
  return map[m?.toLowerCase() ?? ""] ?? m;
}

export function MarketComparisonSection({
  products: _products,
  competitors: _competitors,
}: MarketComparisonSectionProps) {
  const { t } = useTranslation();

  const { data: matrixData, isLoading } = useQuery({
    queryKey: ["analytics", "comparison-matrix"],
    queryFn: async () => {
      const { data } = await analyticsApi.getComparisonMatrix();
      return data;
    },
  });

  const products = matrixData?.products ?? [];
  const competitors = matrixData?.competitors ?? [];
  const matrix = matrixData?.matrix ?? [];

  const getCellColor = (diffPercent: number) => {
    if (diffPercent <= -10) return "bg-emerald-500/80 dark:bg-emerald-600/80";
    if (diffPercent <= -5) return "bg-emerald-400/60 dark:bg-emerald-500/60";
    if (diffPercent <= 0) return "bg-emerald-300/40 dark:bg-emerald-400/40";
    if (diffPercent <= 5) return "bg-amber-300/40 dark:bg-amber-400/40";
    if (diffPercent <= 10) return "bg-amber-400/60 dark:bg-amber-500/60";
    return "bg-red-500/80 dark:bg-red-600/80";
  };

  const handleExportPdf = () => {
    window.print();
  };

  if (isLoading) {
    return (
      <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
        {t("common.loading")}
      </div>
    );
  }

  if (products.length === 0 || competitors.length === 0) {
    return (
      <p className="py-8 text-center text-sm text-muted-foreground">
        {t("competitors.comparisonMatrixEmpty")}
      </p>
    );
  }

  return (
    <div className="space-y-8">
      <div className="flex items-center justify-between">
        <h3 className="text-lg font-semibold">{t("analytics.comparisonMatrix")}</h3>
        <Button variant="outline" size="sm" onClick={handleExportPdf}>
          {t("analytics.exportPdf")}
        </Button>
      </div>

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
              title={`${c.name} (${toMarketplaceDisplay(c.marketplace)})`}
            >
              {c.name}
            </div>
          ))}
          {products.flatMap((p, pi) => [
            <div
              key={`label-${p.id}`}
              className="truncate bg-muted/30 p-2 text-xs dark:bg-muted/20"
              title={p.name}
            >
              {p.name}
            </div>,
            ...competitors.map((c, ci) => {
              const diff = matrix[pi]?.[ci];
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
    </div>
  );
}
