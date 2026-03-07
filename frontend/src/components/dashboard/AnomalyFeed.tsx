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

// TODO: mock when API fails or returns empty
const MOCK_ANOMALIES = [
  {
    id: "1",
    product_id: "mock-1",
    product_name: "iPhone 15 128GB",
    competitor_name: "Ozon",
    change_percent: -12,
    ai_insight: "Competitor running March 8 promo",
    detected_at: new Date(Date.now() - 2 * 60 * 60 * 1000).toISOString(),
    severity: "critical" as Severity,
  },
  {
    id: "2",
    product_id: "mock-2",
    product_name: "Samsung Galaxy S24",
    competitor_name: "Wildberries",
    change_percent: 5,
    ai_insight: "Price increased after stock replenishment",
    detected_at: new Date(Date.now() - 5 * 60 * 60 * 1000).toISOString(),
    severity: "warning" as Severity,
  },
  {
    id: "3",
    product_id: "mock-3",
    product_name: "MacBook Air M3",
    competitor_name: "Ozon",
    change_percent: -8,
    ai_insight: "Flash sale detected",
    detected_at: new Date(Date.now() - 1 * 24 * 60 * 60 * 1000).toISOString(),
    severity: "info" as Severity,
  },
  {
    id: "4",
    product_id: "mock-4",
    product_name: "AirPods Pro 2",
    competitor_name: "Kaspi",
    change_percent: -15,
    ai_insight: "New competitor entered market",
    detected_at: new Date(Date.now() - 3 * 60 * 60 * 1000).toISOString(),
    severity: "critical" as Severity,
  },
  {
    id: "5",
    product_id: "mock-5",
    product_name: "Xiaomi 14",
    competitor_name: "Wildberries",
    change_percent: 3,
    ai_insight: "Minor adjustment, monitor",
    detected_at: new Date(Date.now() - 30 * 60 * 1000).toISOString(),
    severity: "info" as Severity,
  },
];

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
          })
        )
      : MOCK_ANOMALIES;

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
    <div className="max-h-[400px] space-y-2 overflow-y-auto rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg dark:bg-zinc-900/60 dark:border-border/50">
      <h3 className="mb-3 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("dashboard.anomalies.title")}
      </h3>
      {anomalies.slice(0, 5).map((item, i) => (
        <motion.div
          key={item.id ?? i}
          initial={{ opacity: 0, y: 10 }}
          animate={{ opacity: 1, y: 0 }}
          transition={{ delay: 0.15 + i * 0.05 }}
          className={cn(
            "flex gap-3 rounded-lg border border-border/50 bg-background/50 p-3 transition-colors hover:bg-accent/30 dark:border-border/50"
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
              if (item.product_id && !item.product_id.startsWith("mock")) {
                navigate(`/products/${item.product_id}`);
              } else {
                navigate("/products");
              }
            }}
          >
            {t("dashboard.anomalies.view")}
          </Button>
        </motion.div>
      ))}
    </div>
  );
}
