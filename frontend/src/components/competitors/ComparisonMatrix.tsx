/**
 * Heatmap: rows = my products, columns = competitors.
 * Cell color: green (I'm cheaper) to red (I'm more expensive).
 * TODO: GET /api/analytics/comparison-matrix
 */

import { useTranslation } from "react-i18next";
import { formatPrice } from "@/lib/formatters";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { cn } from "@/lib/utils";

export interface ComparisonCell {
  myPrice: number;
  competitorPrice: number;
  diffPercent: number;
}

export interface ComparisonMatrixData {
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
  cells: Record<string, Record<string, ComparisonCell>>;
}

interface ComparisonMatrixProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  products: { id: string; name: string }[];
  competitors: { id: string; name: string }[];
}

/** Mock comparison matrix data. */
function mockMatrixData(
  products: { id: string; name: string }[],
  competitors: { id: string; name: string }[]
): ComparisonMatrixData {
  const cells: Record<string, Record<string, ComparisonCell>> = {};
  const basePrice = 45000;
  products.forEach((p, pi) => {
    cells[p.id] = {};
    competitors.forEach((c, ci) => {
      const myP = basePrice + pi * 2000 + (p.id.charCodeAt(0) % 500);
      const compP = myP * (0.9 + (ci * 0.05) + ((c.id.charCodeAt(0) % 10) / 100));
      const diffPercent = ((myP - compP) / compP) * 100;
      cells[p.id][c.id] = {
        myPrice: myP,
        competitorPrice: compP,
        diffPercent,
      };
    });
  });
  return { products, competitors, cells };
}

export function ComparisonMatrix({
  open,
  onOpenChange,
  products,
  competitors,
}: ComparisonMatrixProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const data = mockMatrixData(products, competitors);

  const getCellColor = (diffPercent: number) => {
    if (diffPercent <= -10) return "bg-emerald-500/80 dark:bg-emerald-600/80";
    if (diffPercent <= -5) return "bg-emerald-400/60 dark:bg-emerald-500/60";
    if (diffPercent <= 0) return "bg-emerald-300/40 dark:bg-emerald-400/40";
    if (diffPercent <= 5) return "bg-amber-300/40 dark:bg-amber-400/40";
    if (diffPercent <= 10) return "bg-amber-400/60 dark:bg-amber-500/60";
    return "bg-red-500/80 dark:bg-red-600/80";
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
          {products.length === 0 || competitors.length === 0 ? (
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
                    const cell = data.cells[p.id]?.[c.id];
                    if (!cell)
                      return (
                        <div key={`${p.id}-${c.id}`} className="bg-background p-1" />
                      );
                    return (
                      <div
                        key={`${p.id}-${c.id}`}
                        className={cn(
                          "flex min-h-[44px] cursor-default items-center justify-center p-1 text-xs transition-colors hover:ring-2 hover:ring-ring",
                          getCellColor(cell.diffPercent)
                        )}
                        title={`${t("competitors.myPrice")}: ${formatPrice(cell.myPrice, "RUB", locale)} | ${c.name}: ${formatPrice(cell.competitorPrice, "RUB", locale)} (${cell.diffPercent > 0 ? "+" : ""}${cell.diffPercent.toFixed(1)}%)`}
                      >
                        {cell.diffPercent > 0 ? "+" : ""}
                        {cell.diffPercent.toFixed(0)}%
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
