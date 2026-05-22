// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Analytics page: 3 tabs (Trends, Forecasts, Market Comparison).
 * i18n: analytics.*, dashboard.*, common.*
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Sparkles } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { formatChartDate } from "@/lib/formatters";
import {
  Area,
  AreaChart,
  XAxis,
  YAxis,
  CartesianGrid,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { productsApi } from "@/api/products";
import { competitorsApi } from "@/api/competitors";
import { analyticsApi } from "@/api/analytics";
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
import { MarketComparisonSection } from "@/components/analytics/MarketComparisonSection";

type Period = "7d" | "30d" | "90d";

function getPeriodDays(period: Period): number {
  switch (period) {
    case "7d": return 7;
    case "30d": return 30;
    case "90d": return 90;
  }
}

export function AnalyticsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const [period, setPeriod] = useState<Period>("30d");
  const [category, setCategory] = useState<string>("all");
  const [competitorFilter, setCompetitorFilter] = useState<string[]>([]);

  const days = getPeriodDays(period);

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

  const { data: trendData } = useQuery({
    queryKey: ["dashboard", "aggregate-trend", days],
    queryFn: async () => {
      const { data } = await analyticsApi.getAggregateTrend(days, 14);
      return data;
    },
  });

  const { data: marketForecast } = useQuery({
    queryKey: ["analytics", "market-forecast"],
    queryFn: async () => {
      const { data } = await analyticsApi.getMarketForecast(14);
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

  const forecastData =
    trendData?.forecast_labels?.map((date, i) => ({
      date,
      dateLabel: formatChartDate(new Date(date), locale),
      forecast: trendData.forecast.at(i) ?? 0,
    })) ?? [];

  const marketText = marketForecast?.summary ?? marketForecast?.text ?? "";
  const marketConfidence = marketForecast?.confidence != null
    ? Math.round(
        typeof marketForecast.confidence === "number" && marketForecast.confidence <= 1
          ? marketForecast.confidence * 100
          : (marketForecast.confidence as number)
      )
    : 0;

  return (
    <div className="space-y-7">
      <PageHeader title="nav.analytics" />

      <Tabs defaultValue="trends">
        <TabsList className="glass-card w-full flex-wrap rounded-2xl p-1.5 sm:w-auto">
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
              <SelectTrigger className="w-full min-w-0 sm:w-40">
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
              <SelectTrigger className="w-full min-w-0 sm:w-48">
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

          <div className="glass-card rounded-2xl p-5">
            <h3 className="mb-3 flex items-center gap-2 text-base font-semibold">
              <Sparkles className="size-4" />
              {t("analytics.aiSummary")}
            </h3>
            <p className="text-sm text-muted-foreground">
              {t("analytics.aiSummaryEmpty")}
            </p>
          </div>
        </TabsContent>

        <TabsContent value="forecasts" className="mt-6 space-y-6">
          <div className="grid gap-6 lg:grid-cols-2">
            <div className="space-y-4">
              <h3 className="text-base font-semibold">{t("analytics.priceForecast14d")}</h3>
              <div className="glass-card h-72 rounded-2xl p-5">
                {forecastData.length > 0 ? (
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
                            </div>
                          );
                        }}
                      />
                      <Area
                        type="monotone"
                        dataKey="forecast"
                        stroke="hsl(var(--primary))"
                        strokeWidth={2}
                        fill="url(#forecastGrad)"
                      />
                    </AreaChart>
                  </ResponsiveContainer>
                ) : (
                  <div className="flex h-full items-center justify-center text-sm text-muted-foreground">
                    {t("analytics.noForecastData")}
                  </div>
                )}
              </div>
            </div>

            <div className="space-y-4">
              <h3 className="text-base font-semibold">{t("analytics.marketForecastQuestion")}</h3>
              <div className="glass-card rounded-2xl p-5">
                {marketText ? (
                  <>
                    <p className="mb-4 text-sm text-muted-foreground">
                      {marketText}
                    </p>
                    {marketConfidence > 0 && (
                      <div>
                        <p className="mb-2 text-xs text-muted-foreground">
                          {t("analytics.confidence")}: {marketConfidence}%
                        </p>
                        <Progress value={marketConfidence} className="h-2" />
                      </div>
                    )}
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    {t("analytics.noMarketForecast")}
                  </p>
                )}
              </div>
            </div>
          </div>

        </TabsContent>

        <TabsContent value="comparison" className="mt-6">
          <div className="glass-card rounded-2xl p-6">
            <MarketComparisonSection products={productList} competitors={competitorList} />
          </div>
        </TabsContent>
      </Tabs>
    </div>
  );
}
