/**
 * Heatmap: rows = my products, columns = competitors.
 * Cell color: green (I'm cheaper) to red (I'm more expensive).
 * Data: GET /api/analytics/comparison-matrix
 */

import { useTranslation } from "react-i18next";
import { safeFixed } from "@/lib/safeNumber";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";

interface ComparisonMatrixProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  products?: { id: string; name: string }[];
  competitors?: { id: string; name: string }[];
}

function toMarketplaceDisplay(m: string): string {
  if (!m) return "";
  return m.replace(/_/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export function ComparisonMatrix({
  open,
  onOpenChange,
}: ComparisonMatrixProps) {
  const { t } = useTranslation();

  const { data: matrixData, isLoading } = useQuery({
    queryKey: ["analytics", "comparison-matrix"],
    queryFn: async () => {
      const { data } = await analyticsApi.getComparisonMatrix();
      return data;
    },
    enabled: open,
  });

  const products = matrixData?.products ?? [];
  const competitors = matrixData?.competitors ?? [];
  const matrix = matrixData?.matrix ?? [];

  const getCellColor = (diffPercent: number) => {
    if (diffPercent <= -10) return "var(--cell-green-80)";
    if (diffPercent <= -5) return "var(--cell-green-60)";
    if (diffPercent <= 0) return "var(--cell-green-40)";
    if (diffPercent <= 5) return "var(--cell-amber-40)";
    if (diffPercent <= 10) return "var(--cell-amber-60)";
    return "var(--cell-red-80)";
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[90vh] max-w-4xl overflow-auto">
        <DialogHeader>
          <DialogTitle>{t("competitors.comparisonMatrix")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-4">
          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
            {t("competitors.comparisonMatrixHint")}
          </p>
          {isLoading ? (
            <div className="flex items-center justify-center py-12 text-sm text-muted-foreground">
              {t("common.loading")}
            </div>
          ) : products.length === 0 || competitors.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("competitors.comparisonMatrixEmpty")}
            </p>
          ) : (
            <div className="overflow-x-auto">
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
                    const diff = matrix.at(pi)?.at(ci);
                    if (diff == null)
                      return (
                        <div key={`${p.id}-${c.id}`} className="bg-background p-1" />
                      );
                    return (
                      <div
                        key={`${p.id}-${c.id}`}
                        className="flex min-h-[44px] cursor-default items-center justify-center p-1 text-xs transition-colors hover:ring-2 hover:ring-ring"
                        style={{ background: getCellColor(diff) }}
                        title={`${c.name}: ${diff > 0 ? "+" : ""}${safeFixed(diff, 1)}%`}
                      >
                        {diff > 0 ? "+" : ""}
                        {safeFixed(diff, 0)}%
                      </div>
                    );
                  }),
                ])}
              </div>
            </div>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
