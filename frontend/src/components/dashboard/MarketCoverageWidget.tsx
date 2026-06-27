import { useMemo } from "react";
import { useQuery } from "@tanstack/react-query";
import { Globe } from "lucide-react";
import { useTranslation } from "react-i18next";
import {
  marketsApi,
  marketsQueryKeys,
  type CoverageRow,
} from "@/api/markets";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { getCountryByCode } from "@/lib/countries";

function parseSharePct(value: number | string | null | undefined): number | null {
  if (value == null || value === "") {
    return null;
  }
  const parsed = typeof value === "number" ? value : Number(value);
  return Number.isFinite(parsed) ? parsed : null;
}

function CoverageRowBar({
  row,
  mode,
}: {
  row: CoverageRow;
  mode: "countries" | "marketplaces";
}) {
  const { t } = useTranslation();
  const share = parseSharePct(row.share_pct);

  const label =
    mode === "countries" && row.country_code
      ? (() => {
          const i18nKey = `countries.${row.country_code}`;
          const localized = t(i18nKey);
          if (localized !== i18nKey) {
            const flag = getCountryByCode(row.country_code)?.flag;
            return flag ? `${flag} ${localized}` : localized;
          }
          const flag = getCountryByCode(row.country_code)?.flag;
          return flag ? `${flag} ${row.label}` : row.label;
        })()
      : row.label;

  return (
    <li className="space-y-1.5">
      <div className="flex items-center justify-between gap-2 text-xs">
        <div className="flex min-w-0 items-center gap-2">
          {mode === "marketplaces" ? (
            <MarketplaceBadge
              marketplace={row.marketplace_domain ?? row.key}
              label={label}
              size="sm"
            />
          ) : (
            <span className="truncate font-medium">{label}</span>
          )}
        </div>
        <span className="shrink-0 tabular-nums text-muted-foreground">{row.count}</span>
      </div>
      {share != null ? (
        <Progress value={share} max={100} className="h-1.5" />
      ) : (
        <div className="h-1.5 w-full rounded-full bg-muted" />
      )}
    </li>
  );
}

function CoverageSkeleton() {
  return (
    <div className="space-y-3" data-testid="coverage-skeleton">
      {Array.from({ length: 4 }, (_, index) => (
        <div key={index} className="space-y-1.5">
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-1.5 w-full" />
        </div>
      ))}
    </div>
  );
}

export interface MarketCoverageWidgetProps {
  countryCode: string | null;
  marketplaceId?: string;
}

export function MarketCoverageWidget({
  countryCode,
  marketplaceId,
}: MarketCoverageWidgetProps) {
  const { t } = useTranslation();

  const queryParams = useMemo(
    () => ({
      country_code: countryCode ?? undefined,
      marketplace_id: marketplaceId,
    }),
    [countryCode, marketplaceId],
  );

  const { data, isLoading, isError } = useQuery({
    queryKey: marketsQueryKeys.geoCoverage(queryParams),
    queryFn: () => marketsApi.getGeoCoverage(queryParams).then((response) => response.data),
    staleTime: 30_000,
  });

  const sortedRows = useMemo(() => {
    const rows = data?.rows ?? [];
    return [...rows].sort((left, right) => right.count - left.count);
  }, [data?.rows]);

  const countryLabel = useMemo(() => {
    if (!countryCode) {
      return "";
    }
    const i18nKey = `countries.${countryCode}`;
    const localized = t(i18nKey);
    if (localized !== i18nKey) {
      return localized;
    }
    return getCountryByCode(countryCode)?.name ?? countryCode;
  }, [countryCode, t]);

  const subtitle =
    data?.mode === "marketplaces" && countryCode
      ? t("market.overview.coverage.subtitleMarketplaces", { country: countryLabel })
      : t("market.overview.coverage.subtitleCountries");

  const showEmpty = !isLoading && !isError && (sortedRows.length === 0 || (data?.total ?? 0) === 0);

  return (
    <div className="surface-base flex h-full flex-col rounded-xl p-3.5">
      <div className="mb-3">
        <h3 className="text-sm font-semibold">{t("market.overview.coverage.title")}</h3>
        <p className="mt-0.5 text-2xs text-muted-foreground">{subtitle}</p>
      </div>

      {isLoading ? (
        <CoverageSkeleton />
      ) : isError ? (
        <p className="text-sm text-muted-foreground">{t("market.overview.coverage.loadError")}</p>
      ) : showEmpty ? (
        <EmptyState
          title="market.overview.coverage.empty"
          description="market.overview.coverage.emptyHint"
          icon={Globe}
          className="py-8"
        />
      ) : (
        <ul className="space-y-3">
          {sortedRows.map((row) => (
            <CoverageRowBar key={row.key} row={row} mode={data?.mode ?? "countries"} />
          ))}
        </ul>
      )}
    </div>
  );
}
