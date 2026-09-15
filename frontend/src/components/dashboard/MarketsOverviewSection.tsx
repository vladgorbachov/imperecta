/**
 * Overview dashboard — the command center.
 * Answers "what changed and does it need action": scope bar, KPI band,
 * movers feed, price-trend hero, coverage, alerts stream, compact news.
 * The catalog lives on the Products page, not here.
 */

import { useEffect, useMemo } from "react";
import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle } from "lucide-react";
import { marketsApi, marketsQueryKeys, type MovementsQueryParams } from "@/api/markets";
import { AlertsStreamWidget } from "@/components/dashboard/AlertsStreamWidget";
import { MarketMoversWidget } from "@/components/dashboard/MarketMoversWidget";
import { MarketCoverageWidget } from "@/components/dashboard/MarketCoverageWidget";
import { MarketTrendWidget } from "@/components/dashboard/MarketTrendWidget";
import { MarketNewsWidget } from "@/components/dashboard/MarketNewsWidget";
import { ScopeBar } from "@/components/dashboard/ScopeBar";
import { useDisplayCurrency } from "@/hooks/useDisplayCurrency";
import { formatRelativeTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { useDashboardCountryStore } from "@/stores/dashboardCountryStore";

/** 7-day mini sparkline; renders only when history points exist (no mock data). */
function KpiSparkline({ points }: { points: number[] }) {
  if (points.length < 2) {
    return null;
  }
  const min = Math.min(...points);
  const max = Math.max(...points);
  const range = max - min || 1;
  const coords = points
    .map((point, index) => {
      const x = (index / (points.length - 1)) * 64;
      const y = 18 - ((point - min) / range) * 14 + 2;
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");
  return (
    <svg viewBox="0 0 64 22" width="64" height="22" aria-hidden className="shrink-0">
      <polyline
        points={coords}
        fill="none"
        stroke="var(--accent)"
        strokeWidth="1.5"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  );
}

function KpiCard({
  label,
  value,
  error,
  title,
  pending = false,
  spark,
}: {
  label: string;
  value: string;
  error?: { onRetry: () => void; title: string };
  title?: string;
  /** Data not accumulated yet — render the honest-empty text small and muted. */
  pending?: boolean;
  /** Optional 7d history for the sparkline (wired once GET /markets/kpi-history lands). */
  spark?: number[];
}) {
  return (
    <div className="surface-base rounded-lg p-3">
      <div className="flex items-center justify-between gap-2">
        <p className="label-mono">{label}</p>
        {spark ? <KpiSparkline points={spark} /> : null}
      </div>
      <div className="mt-1 flex items-center gap-1.5">
        <p
          className={cn(
            "tabular-nums",
            pending
              ? "text-sm text-muted-foreground"
              : "text-2xl font-semibold"
          )}
          style={{ fontFamily: "var(--font-display)" }}
          title={title}
        >
          {value}
        </p>
        {error && (
          <button
            type="button"
            onClick={error.onRetry}
            title={error.title}
            className="shrink-0 text-destructive transition-colors hover:text-destructive/80"
          >
            <AlertTriangle className="size-3.5" />
          </button>
        )}
      </div>
    </div>
  );
}

export function MarketsOverviewSection() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const { apiParam: displayCurrency } = useDisplayCurrency();

  const selectedCountry = useDashboardCountryStore((state) => state.selectedCountry);
  const setCountryOptions = useDashboardCountryStore((state) => state.setCountryOptions);
  const setOptionsLoading = useDashboardCountryStore((state) => state.setOptionsLoading);

  const {
    data: poolStats,
    isError: poolStatsError,
    refetch: refetchPoolStats,
  } = useQuery({
    queryKey: marketsQueryKeys.poolStats(),
    queryFn: () => marketsApi.getPoolStats().then((response) => response.data),
    staleTime: 60_000,
  });

  const {
    data: countryRollup,
    isLoading: countryRollupLoading,
  } = useQuery({
    queryKey: marketsQueryKeys.geoCoverage({}),
    queryFn: () => marketsApi.getGeoCoverage({}).then((response) => response.data),
    staleTime: 30_000,
  });

  const countryOptions = useMemo(() => {
    if (countryRollup?.mode !== "countries") {
      return [];
    }
    return countryRollup.rows
      .filter((row) => row.country_code)
      .map((row) => ({
        code: row.country_code as string,
        label: row.label,
      }));
  }, [countryRollup]);

  useEffect(() => {
    setCountryOptions(countryOptions);
  }, [countryOptions, setCountryOptions]);

  useEffect(() => {
    setOptionsLoading(countryRollupLoading);
  }, [countryRollupLoading, setOptionsLoading]);

  const kpiScopeParams = useMemo((): Pick<MovementsQueryParams, "country_code"> => {
    return selectedCountry ? { country_code: selectedCountry } : {};
  }, [selectedCountry]);

  const movementsFilterParams = useMemo(
    (): MovementsQueryParams => ({
      period: "24h",
      threshold: 5,
      ...kpiScopeParams,
    }),
    [kpiScopeParams],
  );

  const {
    data: dashboardKpi,
    isLoading: dashboardKpiLoading,
    isError: dashboardKpiError,
    refetch: refetchDashboardKpi,
  } = useQuery({
    queryKey: marketsQueryKeys.dashboardKpi(kpiScopeParams),
    queryFn: () => marketsApi.getDashboardKpi(kpiScopeParams).then((response) => response.data),
    staleTime: 30_000,
  });

  const {
    data: moversKpi,
    isLoading: moversKpiLoading,
    isError: moversKpiError,
    refetch: refetchMoversKpi,
  } = useQuery({
    queryKey: marketsQueryKeys.movementsKpi(movementsFilterParams),
    queryFn: () => marketsApi.getMoversKpi(movementsFilterParams).then((response) => response.data),
    staleTime: 30_000,
  });
  const {
    data: moversSummary,
    isLoading: moversSummaryLoading,
    isError: moversSummaryError,
    refetch: refetchMoversSummary,
  } = useQuery({
    queryKey: marketsQueryKeys.movementsSummary(movementsFilterParams),
    queryFn: () =>
      marketsApi.getMoversSummary(movementsFilterParams).then((response) => response.data),
    staleTime: 30_000,
  });
  const {
    data: moversCoverage,
    isLoading: moversCoverageLoading,
    isError: moversCoverageError,
    refetch: refetchMoversCoverage,
  } = useQuery({
    queryKey: marketsQueryKeys.movementsCoverage(movementsFilterParams),
    queryFn: () =>
      marketsApi.getMoversCoverage(movementsFilterParams).then((response) => response.data),
    staleTime: 30_000,
  });

  const movementsDataReady = moversCoverage?.data_ready === true;
  const movementsKpisPending =
    moversKpiLoading || moversSummaryLoading || moversCoverageLoading;
  const movementsKpisErrored =
    moversKpiError || moversSummaryError || moversCoverageError;

  const updated24hValue = useMemo(() => {
    if (dashboardKpiLoading || dashboardKpiError || dashboardKpi == null) {
      return t("common.dash");
    }
    return String(dashboardKpi.updated_24h);
  }, [dashboardKpi, dashboardKpiError, dashboardKpiLoading, t]);

  const lastUpdateValue = useMemo(() => {
    if (dashboardKpiLoading || dashboardKpiError) {
      return t("common.dash");
    }
    if (!dashboardKpi?.last_update) {
      return t("common.dash");
    }
    return formatRelativeTime(dashboardKpi.last_update, locale);
  }, [dashboardKpi, dashboardKpiError, dashboardKpiLoading, locale, t]);

  const lastUpdateTitle = useMemo(() => {
    if (dashboardKpiLoading || dashboardKpiError || !dashboardKpi?.last_update) {
      return undefined;
    }
    return new Date(dashboardKpi.last_update).toLocaleString(locale);
  }, [dashboardKpi, dashboardKpiError, dashboardKpiLoading, locale]);

  const changedMore5Value = useMemo(() => {
    if (movementsKpisPending || movementsKpisErrored) {
      return t("common.dash");
    }
    if (!movementsDataReady) {
      return t("market.overview.kpi.accumulatingData");
    }
    return String(moversKpi?.count ?? t("common.dash"));
  }, [movementsKpisPending, movementsKpisErrored, movementsDataReady, moversKpi, t]);

  const avgVolatilityValue = useMemo(() => {
    if (movementsKpisPending || movementsKpisErrored) {
      return t("common.dash");
    }
    if (!movementsDataReady) {
      return t("market.overview.kpi.accumulatingData");
    }
    if (moversSummary?.avg_abs_change == null) {
      return t("common.dash");
    }
    const numeric = Number(moversSummary.avg_abs_change);
    if (Number.isNaN(numeric)) {
      return t("common.dash");
    }
    return `${numeric.toFixed(2)}%`;
  }, [movementsKpisPending, movementsKpisErrored, movementsDataReady, moversSummary, t]);

  const accumulatingHint = t("market.overview.kpi.accumulatingDataHint");
  const movementsPendingState =
    !movementsDataReady && !movementsKpisPending && !movementsKpisErrored;

  const totalPoolKpi = poolStatsError
    ? null
    : poolStats?.total_products ?? null;

  const movementsRetry = () => {
    void refetchMoversKpi();
    void refetchMoversSummary();
    void refetchMoversCoverage();
  };

  return (
    <section className="space-y-3">
      <ScopeBar />

      <div className="grid gap-2.5 md:grid-cols-2 xl:grid-cols-5">
        <KpiCard
          label={t("market.overview.kpi.totalPool")}
          value={totalPoolKpi == null ? t("common.dash") : String(totalPoolKpi)}
          error={
            poolStatsError
              ? { onRetry: () => refetchPoolStats(), title: t("common.error") }
              : undefined
          }
        />
        <KpiCard
          label={t("market.overview.kpi.updated24h")}
          value={updated24hValue}
          error={
            dashboardKpiError
              ? {
                  onRetry: () => {
                    void refetchDashboardKpi();
                  },
                  title: t("common.error"),
                }
              : undefined
          }
        />
        <KpiCard
          label={t("market.overview.kpi.changedMore5")}
          value={changedMore5Value}
          pending={movementsPendingState}
          title={movementsPendingState ? accumulatingHint : undefined}
          error={
            movementsKpisErrored
              ? { onRetry: movementsRetry, title: t("common.error") }
              : undefined
          }
        />
        <KpiCard
          label={t("market.overview.kpi.avgVolatility")}
          value={avgVolatilityValue}
          pending={movementsPendingState}
          title={movementsPendingState ? accumulatingHint : undefined}
          error={
            movementsKpisErrored
              ? { onRetry: movementsRetry, title: t("common.error") }
              : undefined
          }
        />
        <KpiCard
          label={t("market.overview.kpi.lastUpdate")}
          value={lastUpdateValue}
          title={lastUpdateTitle}
          error={
            dashboardKpiError
              ? {
                  onRetry: () => {
                    void refetchDashboardKpi();
                  },
                  title: t("common.error"),
                }
              : undefined
          }
        />
      </div>

      <div className="grid gap-3 lg:grid-cols-12 lg:items-stretch">
        <div className="min-w-0 lg:col-span-4">
          <MarketMoversWidget
            movementsDataReady={movementsDataReady}
            displayCurrency={displayCurrency}
            countryCode={selectedCountry}
          />
        </div>
        <div className="min-w-0 lg:col-span-8">
          <MarketTrendWidget countryCode={selectedCountry} chartHeight={300} />
        </div>
        <div className="min-w-0 lg:col-span-4">
          <MarketCoverageWidget countryCode={selectedCountry} />
        </div>
        <div className="min-w-0 lg:col-span-4">
          <AlertsStreamWidget />
        </div>
        <div className="min-w-0 lg:col-span-4">
          <MarketNewsWidget countryCode={selectedCountry} />
        </div>
      </div>
    </section>
  );
}
