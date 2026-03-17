import { useTranslation } from "react-i18next";
import { formatPrice } from "@/lib/formatters";
import { TrendBadge } from "./TrendBadge";
import { cn } from "@/lib/utils";

export interface PriceChangeCellProps {
  /** Previous price */
  oldPrice: number;
  /** New price */
  newPrice: number;
  /** Currency code (default RUB) */
  currency?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Displays price change: old price (strikethrough) → new price with inline TrendBadge.
 * Uses locale-aware formatting from i18n.
 */
export function PriceChangeCell({
  oldPrice,
  newPrice,
  currency = "RUB",
  className,
}: PriceChangeCellProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language;

  const diff = newPrice - oldPrice;
  const percent = oldPrice !== 0 ? (diff / oldPrice) * 100 : 0;
  const trend = percent > 0 ? "up" : percent < 0 ? "down" : "stable";

  const arrow = t("ui.priceChangeArrow");

  return (
    <span className={cn("inline-flex flex-wrap items-center gap-2", className)}>
      <span className="line-through" style={{ color: "var(--foreground-muted)" }}>
        {formatPrice(oldPrice, currency, locale)}
      </span>
      <span style={{ color: "var(--foreground-muted)" }}>{arrow}</span>
      <span className="font-medium" style={{ color: "var(--foreground)" }}>
        {formatPrice(newPrice, currency, locale)}
      </span>
      <TrendBadge trend={trend} value={Math.abs(percent)} size="sm" />
    </span>
  );
}
