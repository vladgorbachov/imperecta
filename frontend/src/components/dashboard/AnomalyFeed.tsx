/**
 * Anomaly feed: vertical list of anomaly cards.
 * Data: GET /api/analytics/dashboard/anomalies
 * TODO: if endpoint returns no product_id, add to API for "View" link.
 */

import { useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { motion } from "framer-motion";
import { useQuery } from "@tanstack/react-query";
import { analyticsApi } from "@/api/analytics";
import { formatRelativeTime } from "@/lib/formatters";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";

type Severity = "critical" | "warning" | "info";

const SEVERITY_COLORS: Record<Severity, string> = {
  critical: "bg-price-up",
  warning: "bg-amber-500",
  info: "bg-blue-500",
};

interface AnomalyItem {
  id?: string;
  product_id?: string;
  product_name: string;
  competitor_name: string;
  change_percent: number;
  ai_insight?: string;
  detected_at: string;
  severity?: Severity;
}

function mapApiToAnomaly(item: {
  product_name: string;
  competitor_name: string;
  change_percent: number;
  detected_at: string;
  product_id?: string;
}): AnomalyItem {
  const abs = Math.abs(item.change_percent);
  const severity: Severity = abs >= 10 ? "critical" : abs >= 5 ? "warning" : "info";
  return {
    ...item,
    id: item.product_id,
    severity,
    ai_insight: undefined,
  };
}

export function AnomalyFeed() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;
  const navigate = useNavigate();

  const { data: apiResponse, isLoading, isError } = useQuery({
    queryKey: ["dashboard", "anomalies"],
    queryFn: () => analyticsApi.getDashboardAnomalies().then((r) => r.data),
  });
  const apiItems = apiResponse?.items;

  useEffect(() => {
    if (isError) toast.error(t("common.error"));
  }, [isError, t]);

  const anomalies: AnomalyItem[] =
    apiItems && apiItems.length > 0
      ? apiItems.map((a) =>
          mapApiToAnomaly({
            product_name: a.product_name,
            competitor_name: a.competitor_name,
            change_percent: a.change_percent,
            detected_at: a.detected_at,
            product_id: a.product_id,
          })
        )
      : [];

  if (isLoading) {
    return (
      <div className="space-y-2">
        {[0, 1, 2, 3, 4].map((i) => (
          <Skeleton key={i} className="h-24 rounded-lg" />
        ))}
      </div>
    );
  }

  if (isError) {
    return (
      <div className="rounded-xl border border-destructive/30 bg-destructive/5 p-4">
        <p className="text-sm text-destructive">{t("common.error")}</p>
      </div>
    );
  }

  return (
    <div className="max-h-[400px] space-y-2 overflow-y-auto rounded-xl border border-border bg-card p-4 shadow-sm scrollbar-hide dark:border-border">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("dashboard.anomalies.title")}
      </h3>
      {anomalies.length === 0 ? (
        <p className="py-6 text-center text-sm text-muted-foreground">
          {t("dashboard.anomaliesEmpty")}
        </p>
      ) : (
        anomalies.slice(0, 5).map((item, i) => (
        <motion.div
          key={item.id ?? i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 + i * 0.05 }}
          className={cn(
            "flex gap-3 rounded-lg border border-border bg-muted/50 p-3 transition-colors hover:bg-muted dark:border-border"
          )}
        >
          <div
            className={cn(
              "w-1 shrink-0 rounded-full",
              SEVERITY_COLORS[item.severity ?? "info"]
            )}
          />
          <div className="min-w-0 flex-1">
            <p className="text-sm font-medium">
              {item.competitor_name}: {item.product_name}{" "}
              <span
                className={cn(
                  item.change_percent < 0 ? "text-price-down" : "text-price-up"
                )}
              >
                {item.change_percent > 0 ? "+" : ""}
                {item.change_percent.toFixed(0)}%
              </span>
            </p>
            {item.ai_insight && (
              <p className="mt-0.5 text-xs italic text-muted-foreground">
                AI: {item.ai_insight}
              </p>
            )}
            <p className="mt-1 text-xs text-muted-foreground">
              {formatRelativeTime(item.detected_at, locale)}
            </p>
          </div>
          <Button
            variant="ghost"
            size="sm"
            className="shrink-0"
            onClick={() => {
              if (item.product_id) {
                navigate(`/products/${item.product_id}`);
              } else {
                navigate("/products");
              }
            }}
          >
            {t("dashboard.anomalies.view")}
          </Button>
        </motion.div>
      ))
      )}
    </div>
  );
}
