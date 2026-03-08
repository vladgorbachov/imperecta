// MOBILE-2026: fully responsive + bottom nav + drawer
// Compact version: max-height 150px, single-line layout

/**
 * Scenario simulator: "What if" price change slider.
 * TODO: create POST /api/analytics/simulate-scenario
 * Frontend-only linear interpolation for now.
 */

import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Slider } from "@/components/ui/slider";
import { cn } from "@/lib/utils";

export function ScenarioSimulator() {
  const { t } = useTranslation();
  const [priceChangePercent, setPriceChangePercent] = useState(0);

  const { salesChange, marginForecast, confidence } = useMemo(() => {
    const p = priceChangePercent;
    const salesChange = p <= 0 ? p * 0.5 : p * 0.83;
    const baseMargin = 23.5;
    const marginForecast = baseMargin - Math.abs(p) * 0.08;
    const confidence = Math.max(60, 95 - Math.abs(p) * 0.5);
    return {
      salesChange,
      marginForecast: Math.max(15, marginForecast),
      confidence: Math.round(confidence),
    };
  }, [priceChangePercent]);

  return (
    <motion.div
      initial={{ opacity: 0, y: 20 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ delay: 0.25, duration: 0.3 }}
      className="max-h-[150px] rounded-xl border border-border bg-card p-3 shadow-sm dark:border-border"
    >
      <p className="mb-2 text-sm font-medium">{t("dashboard.simulator.whatIf")}</p>
      <div className="flex flex-wrap items-center gap-3">
        <div className="min-w-[140px] flex-1">
          <div className="flex items-center justify-between gap-2">
            <Slider
              value={[priceChangePercent]}
              onValueChange={([v]) => setPriceChangePercent(v)}
              min={-30}
              max={30}
              step={1}
              className="flex-1 touch-manipulation"
            />
            <span className="w-12 shrink-0 text-right font-mono text-sm font-bold">
              {priceChangePercent >= 0 ? "+" : ""}
              {priceChangePercent}%
            </span>
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-4 text-xs text-muted-foreground">
          <span>
            {t("dashboard.simulator.expectedSales")}{" "}
            <span
              className={cn(
                "font-semibold text-foreground",
                salesChange >= 0 ? "text-price-down" : "text-price-up"
              )}
            >
              {salesChange >= 0 ? "+" : ""}
              {salesChange.toFixed(0)}%
            </span>
          </span>
          <span>
            {t("dashboard.simulator.marginForecast")}{" "}
            <span className="font-semibold text-foreground">
              {marginForecast.toFixed(1)}%
            </span>
          </span>
          <span>
            {t("dashboard.simulator.confidence")}: {confidence}%
          </span>
          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-muted">
            <div
              className="h-full rounded-full bg-primary transition-all"
              style={{ width: `${confidence}%` }}
            />
          </div>
        </div>
      </div>
    </motion.div>
  );
}
