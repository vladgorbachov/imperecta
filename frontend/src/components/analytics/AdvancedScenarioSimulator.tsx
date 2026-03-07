/**
 * Extended scenario simulator with 5 sliders.
 * TODO: POST /api/analytics/advanced-simulation
 */

import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Slider } from "@/components/ui/slider";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

type SeasonalFactor = "normal" | "holidays" | "sale";

export function AdvancedScenarioSimulator() {
  const { t } = useTranslation();
  const [pricePercent, setPricePercent] = useState(0);
  const [volumePercent, setVolumePercent] = useState(0);
  const [adBudgetPercent, setAdBudgetPercent] = useState(0);
  const [inflationPercent, setInflationPercent] = useState(0);
  const [seasonalFactor, setSeasonalFactor] = useState<SeasonalFactor>("normal");

  const { profitForecast, confidence } = useMemo(() => {
    const p = pricePercent;
    const v = volumePercent;
    const a = adBudgetPercent;
    const inf = inflationPercent;
    const sMult = seasonalFactor === "holidays" ? 1.2 : seasonalFactor === "sale" ? 0.85 : 1;

    const revenueImpact = (1 + p / 100) * (1 + v / 100) * sMult;
    const costImpact = 1 + inf / 100 + a / 100 * 0.3;
    const profitMult = (revenueImpact / costImpact - 1) * 100;
    const profitForecast = Math.max(-30, Math.min(50, profitMult));
    const confidence = Math.max(55, 90 - Math.abs(p) * 0.3 - Math.abs(v) * 0.2);

    return { profitForecast, confidence: Math.round(confidence) };
  }, [pricePercent, volumePercent, adBudgetPercent, inflationPercent, seasonalFactor]);

  const handleCalculate = () => {
    // TODO: POST /api/analytics/advanced-simulation
  };

  return (
    <div className="rounded-xl border border-border bg-card/60 p-4 shadow-sm dark:border-border dark:bg-card/60">
      <h3 className="mb-4 text-sm font-semibold uppercase tracking-wider text-muted-foreground">
        {t("analytics.scenarioSimulator")}
      </h3>

      <div className="space-y-6">
        <div>
          <label className="text-sm text-muted-foreground">
            {t("analytics.simulator.myPrice")}
          </label>
          <Slider
            value={[pricePercent]}
            onValueChange={([v]) => setPricePercent(v)}
            min={-30}
            max={30}
            step={1}
            className="mt-2"
          />
          <p className="mt-1 text-lg font-bold">
            {pricePercent >= 0 ? "+" : ""}{pricePercent}%
          </p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">
            {t("analytics.simulator.volume")}
          </label>
          <Slider
            value={[volumePercent]}
            onValueChange={([v]) => setVolumePercent(v)}
            min={-30}
            max={30}
            step={1}
            className="mt-2"
          />
          <p className="mt-1 text-lg font-bold">
            {volumePercent >= 0 ? "+" : ""}{volumePercent}%
          </p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">
            {t("analytics.simulator.adBudget")}
          </label>
          <Slider
            value={[adBudgetPercent]}
            onValueChange={([v]) => setAdBudgetPercent(v)}
            min={-50}
            max={50}
            step={5}
            className="mt-2"
          />
          <p className="mt-1 text-lg font-bold">
            {adBudgetPercent >= 0 ? "+" : ""}{adBudgetPercent}%
          </p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">
            {t("analytics.simulator.inflation")}
          </label>
          <Slider
            value={[inflationPercent]}
            onValueChange={([v]) => setInflationPercent(v)}
            min={0}
            max={15}
            step={0.5}
            className="mt-2"
          />
          <p className="mt-1 text-lg font-bold">+{inflationPercent}%</p>
        </div>

        <div>
          <label className="text-sm text-muted-foreground">
            {t("analytics.simulator.seasonalFactor")}
          </label>
          <Select
            value={seasonalFactor}
            onValueChange={(v) => setSeasonalFactor(v as SeasonalFactor)}
          >
            <SelectTrigger className="mt-2">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="normal">{t("analytics.simulator.seasonalNormal")}</SelectItem>
              <SelectItem value="holidays">{t("analytics.simulator.seasonalHolidays")}</SelectItem>
              <SelectItem value="sale">{t("analytics.simulator.seasonalSale")}</SelectItem>
            </SelectContent>
          </Select>
        </div>

        <div className="rounded-lg border border-border bg-background/50 p-4 dark:border-border">
          <p className="text-sm text-muted-foreground">
            {t("analytics.simulator.profitForecast")}
          </p>
          <p
            className={cn(
              "text-2xl font-bold",
              profitForecast >= 0 ? "text-price-down" : "text-price-up"
            )}
          >
            {profitForecast >= 0 ? "+" : ""}{profitForecast.toFixed(1)}%
          </p>
          <div className="mt-2">
            <p className="text-xs text-muted-foreground">
              {t("analytics.simulator.confidence")}: {confidence}%
            </p>
            <div className="mt-1 h-2 overflow-hidden rounded-full bg-muted">
              <div
                className="h-full rounded-full bg-primary transition-all"
                style={{ width: `${confidence}%` }}
              />
            </div>
          </div>
        </div>

        <Button onClick={handleCalculate} className="w-full">
          {t("analytics.simulator.calculate")}
        </Button>
      </div>
    </div>
  );
}
