/**
 * Analytics page: 3 tabs (Trends, Forecasts, Market Comparison).
 * i18n: analytics.*, dashboard.*, common.*
 */

import { useState, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { formatChartDate } from "@/lib/formatters";
import {
  Area,
  AreaChart,
  ReferenceArea,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { productsApi } from "@/api/products";
import { competitorsApi } from "@/api/competitors";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Button } from "@/components/ui/button";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Progress } from "@/components/ui/progress";
import { TrendsChart } from "@/components/analytics/TrendsChart";
import { AdvancedScenarioSimulator } from "@/components/analytics/AdvancedScenarioSimulator";
import { MarketComparisonSection } from "@/components/analytics/MarketComparisonSection";

type Period = "7d" | "30d" | "90d";

/** Mock 14-day price forecast with confidence interval. */
function mockForecastData(locale: string) {
  const data: Array<{ date: string; dateLabel: string; forecast: number; low: number; high: number }> = [];
  const base = 45500;
  const now = new Date();
  for (let i = 0; i < 14; i++) {
    const d = new Date(now);
    d.setDate(d.getDate() + i);
    const dateStr = d.toISOString().slice(0, 10);
    const trend = i * 80;
    const noise = () => (Math.random() - 0.5) * 500;
    const f = Math.round(base + trend + noise());
    data.push({
      date: dateStr,
      dateLabel: formatChartDate(d, locale),
      forecast: f,
      low: Math.max(0, f - 800),
      high: f + 1000,
    });
  }
  return data;
}

/** Mock AI trend summary. TODO: GET /api/analytics/trend-summary */
const MOCK_TREND_SUMMARY = [
  "Average prices increased by 2.3% over the last 30 days.",
  "Competitor Ozon reduced prices on 15% of overlapping products.",
  "Seasonality factor suggests a slight upward trend toward the end of the month.",
  "Your products maintain a 5% premium vs. market average.",
];

/** Mock market forecast. TODO: GET /api/analytics/market-forecast */
const MOCK_MARKET_FORECAST = {
  text: "Based on current trends, we expect moderate price pressure in the electronics segment. Competitors may run promotional campaigns in the next 7–10 days. Recommended: monitor Ozon and WB for flash sales.",
  confidence: 87,
};

export function AnalyticsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const [period, setPeriod] = useState<Period>("30d");
  const [category, setCategory] = useState<string>("all");
  const [competitorFilter, setCompetitorFilter] = useState<string[]>([]);

  const { data: productsData } = useQuery({
    queryKey: ["products", "analytics"],
    queryFn: async () => {
      const { data } = await productsApi.list({ limit: 100 });
      return data;
    },
  });
  const { data: competitors = [] } = useQuery({
    queryKey: ["competitors"],
    queryFn: async () => {
      const { data } = await competitorsApi.list();
      return data;
    },
  });
  const { data: categories = [] } = useQuery({
    queryKey: ["products", "categories"],
    queryFn: async () => {
      const { data } = await productsApi.getCategories();
      return data;
    },
  });

  const products = productsData?.items ?? [];
  const filteredProducts =
    category && category !== "all"
      ? products.filter((p) => p.category === category)
      : products;
  const productList = filteredProducts.map((p) => ({ id: p.id, name: p.name }));
  const competitorList = competitors.map((c) => ({ id: c.id, name: c.name }));

  const filteredCompetitorIds = competitorFilter.length > 0
    ? competitorFilter
    : competitorList.map((c) => c.id);

  const forecastData = useMemo(() => mockForecastData(locale), [locale]);

  return (
    <div className="space-y-6">
      <PageHeader title="nav.analytics" />

      <Tabs defaultValue="trends">
        <TabsList className="w-full flex-wrap sm:w-auto">
          <TabsTrigger value="trends">{t("analytics.tabTrends")}</TabsTrigger>
          <TabsTrigger value="forecasts">
            {t("analytics.tabForecasts")} <Sparkles className="ml-1 size-3" />
          </TabsTrigger>
          <TabsTrigger value="comparison">{t("analytics.tabComparison")}</TabsTrigger>
        </TabsList>

        <TabsContent value="trends" className="mt-6 space-y-6">
          <div className="flex flex-wrap gap-2">
            {(["7d", "30d", "90d"] as const).map((p) => (
              <Button
                key={p}
                variant={period === p ? "default" : "outline"}
                size="sm"
                onClick={() => setPeriod(p)}
              >
                {p === "7d" ? "7d" : p === "30d" ? "30d" : "90d"}
              </Button>
            ))}
            <Select value={category} onValueChange={setCategory}>
              <SelectTrigger className="w-40">
                <SelectValue placeholder={t("analytics.categoryFilter")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("products.allCategories")}</SelectItem>
                {categories.map((c) => (
                  <SelectItem key={c} value={c}>
                    {c}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
            <Select
              value={competitorFilter.length === 0 ? "all" : competitorFilter[0]}
              onValueChange={(v) =>
                setCompetitorFilter(v === "all" ? [] : [v])
              }
            >
              <SelectTrigger className="w-48">
                <SelectValue placeholder={t("analytics.competitorFilter")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("analytics.allCompetitors")}</SelectItem>
                {competitors.map((c) => (
                  <SelectItem key={c.id} value={c.id}>
                    {c.name}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          <TrendsChart
            period={period}
            category={category}
            competitorIds={filteredCompetitorIds}
            products={productList}
            competitors={competitorList}
          />

          <div className="rounded-xl border border-border bg-card/60 p-4 shadow-sm dark:border-border dark:bg-card/60">
            <h3 className="mb-3 flex items-center gap-2 text-sm font-semibold">
              <Sparkles className="size-4" />
              {t("analytics.aiSummary")}
            </h3>
            <ul className="list-inside list-disc space-y-1 text-sm text-muted-foreground">
              {MOCK_TREND_SUMMARY.map((s, i) => (
                <li key={i}>{s}</li>
              ))}
            </ul>
          </div>
        </TabsContent>

        <TabsContent value="forecasts" className="mt-6 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <h3 className="text-sm font-semibold">{t("analytics.priceForecast14d")}</h3>
              <div className="h-64 rounded-lg border border-border bg-card/60 p-4 dark:border-border dark:bg-card/60">
                <ResponsiveContainer width="100%" height="100%">
                  <AreaChart data={forecastData} margin={{ top: 10, right: 10, left: 0, bottom: 0 }}>
                    <defs>
                      <linearGradient id="forecastGrad" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stopColor="hsl(var(--primary))" stopOpacity={0.4} />
                        <stop offset="100%" stopColor="hsl(var(--primary))" stopOpacity={0} />
                      </linearGradient>
                    </defs>
                    <CartesianGrid strokeDasharray="3 3" className="stroke-muted" />
                    <XAxis dataKey="dateLabel" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                    <YAxis
                      tick={{ fontSize: 10 }}
                      stroke="hsl(var(--muted-foreground))"
                      tickFormatter={(v) => new Intl.NumberFormat(locale).format(v)}
                    />
                    <Tooltip
                      content={({ active, payload }) => {
                        if (!active || !payload?.length) return null;
                        const p = payload[0]?.payload as (typeof forecastData)[0];
                        return (
                          <div className="rounded-md border border-border bg-card px-3 py-2 shadow-md">
                            <p className="mb-1 font-medium">{p?.dateLabel}</p>
                            <p className="text-xs">
                              {t("analytics.forecast")}: {p?.forecast != null ? new Intl.NumberFormat(locale).format(p.forecast) : "—"}
                            </p>
                            <p className="text-xs text-muted-foreground">
                              {t("analytics.confidenceInterval")}: {p?.low}–{p?.high}
                            </p>
                          </div>
                        );
                      }}
                    />
                    {forecastData.map((_, i) => (
                      <ReferenceArea
                        key={i}
                        x1={i - 0.5}
                        x2={i + 0.5}
                        y1={forecastData[i]?.low ?? 0}
                        y2={forecastData[i]?.high ?? 0}
                        fill="hsl(var(--primary))"
                        fillOpacity={0.15}
                      />
                    ))}
                    <Area
                      type="monotone"
                      dataKey="forecast"
                      stroke="hsl(var(--primary))"
                      strokeWidth={2}
                      fill="url(#forecastGrad)"
                    />
                  </AreaChart>
                </ResponsiveContainer>
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-sm font-semibold">{t("analytics.marketForecastQuestion")}</h3>
              <div className="rounded-xl border border-border bg-card/60 p-4 shadow-sm dark:border-border dark:bg-card/60">
                <p className="mb-4 text-sm text-muted-foreground">
                  {MOCK_MARKET_FORECAST.text}
                </p>
                <div>
                  <p className="mb-2 text-xs text-muted-foreground">
                    {t("analytics.confidence")}: {MOCK_MARKET_FORECAST.confidence}%
                  </p>
                  <Progress value={MOCK_MARKET_FORECAST.confidence} className="h-2" />
                </div>
              </div>
            </div>
          </div>

          <AdvancedScenarioSimulator />
        </TabsContent>

        <TabsContent value="comparison" className="mt-6">
          <div className="rounded-xl border border-border bg-card/60 p-6 shadow-sm dark:border-border dark:bg-card/60">
            <MarketComparisonSection products={productList} competitors={competitorList} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
