/**
 * Shared product table row for the pool and favorites tabs.
 * Columns: star · photo (60px) · name · category · marketplace · country ·
 * price · 24h change. Star toggles the client-side favorite.
 */

import { Star } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { PoolProductItem } from "@/api/products";
import { MarketplaceBadge } from "@/components/ui-custom/MarketplaceBadge";
import { PriceDisplay } from "@/components/ui-custom/PriceDisplay";
import { TableCell, TableHead, TableHeader, TableRow } from "@/components/ui/table";
import { useMarketplaceLabelFormatter } from "@/hooks/useMarketplaceLabel";
import { useFavoritesStore, useIsFavorite } from "@/stores/favoritesStore";
import { cn } from "@/lib/utils";

/** Country code → flag emoji (regional indicators); ZZ (World) → globe. */
export function countryFlag(code?: string | null): string {
  if (!code || code.length !== 2) {
    return "";
  }
  const upper = code.toUpperCase();
  if (upper === "ZZ") {
    return "🌐";
  }
  const base = 0x1f1e6;
  return String.fromCodePoint(
    base + upper.charCodeAt(0) - 65,
    base + upper.charCodeAt(1) - 65,
  );
}

function ProductThumb({ item }: { item: PoolProductItem }) {
  const letter = (item.title || "?")[0].toUpperCase();
  if (item.image_url) {
    return (
      <img
        src={item.image_url}
        alt=""
        loading="lazy"
        className="size-15 shrink-0 rounded-lg border border-[var(--glass-border)] object-cover"
        style={{ width: 60, height: 60 }}
      />
    );
  }
  return (
    <div
      className="flex shrink-0 items-center justify-center rounded-lg text-lg font-semibold"
      style={{
        width: 60,
        height: 60,
        background: "var(--glass-bg)",
        border: "1px solid var(--glass-border)",
        color: "var(--foreground-muted)",
      }}
    >
      {letter}
    </div>
  );
}

export interface ProductRowProps {
  item: PoolProductItem;
  onOpen: (item: PoolProductItem) => void;
}

export function ProductRow({ item, onOpen }: ProductRowProps) {
  const { t } = useTranslation();
  const formatMarketplaceLabel = useMarketplaceLabelFormatter();
  const toggleFavorite = useFavoritesStore((state) => state.toggle);
  const isFavorite = useIsFavorite(item.id);

  const marketplaceLabel =
    formatMarketplaceLabel({
      name: item.marketplace_name,
      domain: item.marketplace_domain,
      countryCode: null,
    }) ||
    item.marketplace_name ||
    item.marketplace_domain ||
    "—";

  return (
    <TableRow
      className="cursor-pointer transition-colors"
      data-trend={
        item.price_change_pct != null && item.price_change_pct > 0
          ? "up"
          : item.price_change_pct != null && item.price_change_pct < 0
            ? "down"
            : undefined
      }
      onClick={() => onOpen(item)}
    >
      <TableCell className="w-10 pe-0">
        <button
          type="button"
          aria-label={t("products.favorite.toggle")}
          aria-pressed={isFavorite}
          className={cn(
            "grid size-7 place-items-center rounded-md transition-colors",
            isFavorite
              ? "text-[var(--color-promo)]"
              : "text-[var(--foreground-subtle)] hover:text-[var(--foreground-muted)]",
          )}
          onClick={(event) => {
            event.stopPropagation();
            toggleFavorite(item);
          }}
        >
          <Star
            className="size-4"
            fill={isFavorite ? "currentColor" : "none"}
          />
        </button>
      </TableCell>
      <TableCell className="w-[76px]">
        <ProductThumb item={item} />
      </TableCell>
      <TableCell className="min-w-[220px]">
        <span className="line-clamp-2 text-[0.9375rem] font-medium leading-snug">
          {item.title || "—"}
        </span>
      </TableCell>
      <TableCell className="w-36">
        {item.category ? (
          <span className="label-mono inline-block max-w-full truncate rounded border border-[var(--glass-border)] px-1.5 py-0.5 align-middle">
            {item.category}
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="w-40">
        <MarketplaceBadge
          marketplace={
            item.marketplace_domain ||
            item.marketplace_name ||
            String(item.marketplace_id)
          }
          label={marketplaceLabel}
          size="sm"
        />
      </TableCell>
      <TableCell className="w-20 whitespace-nowrap">
        {item.country_code ? (
          <span className="inline-flex items-center gap-1.5">
            <span aria-hidden>{countryFlag(item.country_code)}</span>
            <span className="font-mono text-xs text-muted-foreground">
              {item.country_code.toUpperCase()}
            </span>
          </span>
        ) : (
          <span className="text-muted-foreground">—</span>
        )}
      </TableCell>
      <TableCell className="w-32 text-right">
        <PriceDisplay
          localAmount={item.price}
          localCurrency={item.currency}
          displayAmount={item.display_price}
          displayCurrency={item.display_currency}
          conversionAvailable={item.conversion_available}
        />
      </TableCell>
      <TableCell className="w-28 text-right">
        {item.price_change_pct != null ? (
          <span
            className={cn(
              "font-mono font-medium tabular-nums",
              item.price_change_pct > 0 && "text-[var(--color-price-up)]",
              item.price_change_pct < 0 && "text-[var(--color-price-down)]",
            )}
          >
            {item.price_change_pct > 0 ? "+" : ""}
            {item.price_change_pct.toFixed(2)}%
          </span>
        ) : (
          "—"
        )}
      </TableCell>
    </TableRow>
  );
}

/** Shared table header for both tabs. Headers stay nowrap and the table
    scrolls horizontally inside its own container, so long translations in
    any of the 8 locales never break the page layout. */
export function ProductsTableHead() {
  const { t } = useTranslation();
  return (
    <TableHeader>
      <TableRow className="hover:bg-transparent">
        <TableHead className="w-10" />
        <TableHead className="w-[76px]" />
        <TableHead className="min-w-[220px] whitespace-nowrap">{t("products.name")}</TableHead>
        <TableHead className="w-36 whitespace-nowrap">{t("products.category")}</TableHead>
        <TableHead className="w-40 whitespace-nowrap">{t("products.marketplace")}</TableHead>
        <TableHead className="w-20 whitespace-nowrap">{t("products.country")}</TableHead>
        <TableHead className="w-32 whitespace-nowrap text-right">{t("products.price")}</TableHead>
        <TableHead className="w-28 whitespace-nowrap text-right">{t("products.change24h")}</TableHead>
      </TableRow>
    </TableHeader>
  );
}
