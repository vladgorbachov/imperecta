/**
 * Cross-shop price comparison inside Product Peek (P6, data-ops service).
 * Best (cheapest) offer highlighted; prices compared in EUR with the local
 * price secondary; unpriced shops shown with an "updating" badge, low
 * match confidence flagged. Honest pending state while the listing is
 * unmatched — the pool re-matches continuously, so nothing is cached hard.
 */

import { useTranslation } from "react-i18next";
import { useQuery } from "@tanstack/react-query";
import { ExternalLink } from "lucide-react";
import { dataOpsApi, type ComparisonOffer } from "@/api/dataOps";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { Skeleton } from "@/components/ui/skeleton";
import { formatPriceNumber } from "@/lib/formatters";
import { cn } from "@/lib/utils";

const LOW_CONFIDENCE = 0.85;

function OfferRow({
  offer,
  isBest,
  isCurrent,
  locale,
}: {
  offer: ComparisonOffer;
  isBest: boolean;
  isCurrent: boolean;
  locale: string;
}) {
  const { t } = useTranslation();
  const lowConfidence =
    offer.match_confidence != null && offer.match_confidence < LOW_CONFIDENCE;

  return (
    <li
      className={cn(
        "flex items-center gap-2 rounded-md border px-2.5 py-2",
        isBest
          ? "border-[var(--accent-border)] bg-[var(--accent-bg-subtle)]"
          : "border-[var(--glass-border)]",
      )}
    >
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5">
          <MarketplaceBadge
            marketplace={offer.marketplace_code}
            label={offer.marketplace_name}
            size="sm"
          />
          {offer.country_code ? (
            <span className="label-mono">{offer.country_code}</span>
          ) : null}
          {isBest ? (
            <span className="label-mono !text-[var(--status-ok)]">
              {t("comparison.cheapest")}
            </span>
          ) : null}
          {isCurrent ? (
            <span className="label-mono">{t("comparison.current")}</span>
          ) : null}
          {lowConfidence ? (
            <span className="label-mono !text-[var(--status-warn)]">
              {t("comparison.possibleMatch")}
            </span>
          ) : null}
        </div>
        <p className="mt-0.5 truncate text-xs text-muted-foreground">
          {offer.title_en ?? offer.name}
        </p>
      </div>
      <div className="shrink-0 text-right">
        {offer.last_price_eur != null ? (
          <>
            <p className="font-mono text-sm font-medium tabular-nums">
              {formatPriceNumber(offer.last_price_eur, locale)} €
            </p>
            {offer.last_price != null &&
            offer.last_currency_code &&
            offer.last_currency_code !== "EUR" ? (
              <p className="font-mono text-2xs tabular-nums text-muted-foreground">
                {formatPriceNumber(offer.last_price, locale)}{" "}
                {offer.last_currency_code}
              </p>
            ) : null}
          </>
        ) : (
          <p className="text-2xs text-muted-foreground">
            {t("comparison.priceUpdating")}
          </p>
        )}
      </div>
      <a
        href={offer.external_url}
        target="_blank"
        rel="noopener noreferrer"
        className="shrink-0 text-muted-foreground transition-colors hover:text-[var(--foreground)]"
        aria-label={offer.marketplace_name}
      >
        <ExternalLink className="size-3.5" />
      </a>
    </li>
  );
}

export function ComparisonSection({
  listingId,
  enabled,
}: {
  listingId: string;
  enabled: boolean;
}) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";

  const { data, isLoading, isError } = useQuery({
    queryKey: ["listing-comparison", listingId],
    queryFn: () =>
      dataOpsApi.getListingComparison(listingId).then((r) => r.data),
    enabled,
    staleTime: 60_000,
  });

  const group = data?.group ?? null;
  const bestOfferId =
    group?.offers.find((offer) => offer.last_price_eur != null)?.listing_id ??
    null;
  const spread =
    group?.min_price_eur != null && group?.max_price_eur != null
      ? group.max_price_eur - group.min_price_eur
      : null;

  return (
    <div data-testid="comparison-section">
      <div className="mb-1.5 flex items-center justify-between gap-2">
        <p className="label-mono">{t("products.peek.listings")}</p>
        {group ? (
          <span className="label-mono">
            {t("comparison.shops", { count: group.shops })}
          </span>
        ) : null}
      </div>

      {isLoading ? (
        <div className="space-y-1.5">
          <Skeleton className="h-10 w-full rounded-md" />
          <Skeleton className="h-10 w-full rounded-md" />
        </div>
      ) : isError ? (
        <p className="text-sm text-muted-foreground">{t("common.error")}</p>
      ) : group == null || group.offers.length === 0 ? (
        <p className="text-sm text-muted-foreground">
          {t("comparison.unavailable")}
        </p>
      ) : (
        <>
          {spread != null && spread > 0 ? (
            <p className="mb-1.5 text-xs text-muted-foreground">
              {formatPriceNumber(group.min_price_eur ?? 0, locale)}–
              {formatPriceNumber(group.max_price_eur ?? 0, locale)} € ·{" "}
              {t("comparison.spread")}:{" "}
              <span className="font-mono tabular-nums">
                {formatPriceNumber(spread, locale)} €
              </span>
            </p>
          ) : null}
          <ul className="max-h-72 space-y-1.5 overflow-y-auto pr-1">
            {group.offers.map((offer) => (
              <OfferRow
                key={offer.listing_id}
                offer={offer}
                isBest={offer.listing_id === bestOfferId}
                isCurrent={offer.listing_id === listingId}
                locale={locale}
              />
            ))}
          </ul>
        </>
      )}
    </div>
  );
}
