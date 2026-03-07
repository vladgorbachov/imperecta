/**
 * Scenario simulator: "What if" price change slider.
 * TODO: create POST /api/analytics/simulate-scenario
 * Frontend-only linear interpolation for now.
 */

import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

export function ScenarioSimulator() {
  const { t } = useTranslation();
  const [priceChangePercent, setPriceChangePercent] = useState(0);

  // Linear interpolation: -30% -> -15% sales, +30% -> +25% sales
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
      className="rounded-xl border border-border/50 bg-card/60 p-4 shadow-sm backdrop-blur-lg dark:bg-zinc-900/60 dark:border-border/50"
    >
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("dashboard.simulator.title")}
      </h3>
      <p className="mb-2 text-lg font-medium">{t("dashboard.simulator.whatIf")}</p>

      <div className="space-y-4">
        <div>
          <label className="text-sm text-muted-foreground">
            {t("dashboard.simulator.changePrice")}
          </label>
          <Slider
            value={[priceChangePercent]}
            onValueChange={([v]) => setPriceChangePercent(v)}
            min={-30}
            max={30}
            step={1}
            className="mt-2"
          />
          <p className="mt-1 text-2xl font-bold">
            {priceChangePercent >= 0 ? "+" : ""}
            {priceChangePercent}%
          </p>
        </div>

        <div className="space-y-2 rounded-lg border border-border/50 bg-background/50 p-3 dark:border-border/50">
          <p className="text-sm">
            {t("dashboard.simulator.expectedSales")}{" "}
            <span
              className={cn(
                "font-bold",
                salesChange >= 0 ? "text-price-down" : "text-price-up"
              )}
            >
              {salesChange >= 0 ? "+" : ""}
              {salesChange.toFixed(0)}%
            </span>
          </p>
          <p className="text-sm">
            {t("dashboard.simulator.marginForecast")}{" "}
            <span className="font-bold">
              {marginForecast.toFixed(1)}%
            </span>
          </p>
          <div>
            <p className="text-sm text-muted-foreground">
              {t("dashboard.simulator.confidence")}: {confidence}%
            </p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${confidence}%` }}
              />
            </div>
          </div>
        </div>

        <Button disabled className="w-full">
          {t("dashboard.simulator.applyRecommendation")}
        </Button>
      </div>
    </motion.div>
  );
}
