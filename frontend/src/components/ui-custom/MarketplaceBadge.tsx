import { useTranslation } from "react-i18next";
import { MARKETPLACE_COLORS } from "@/lib/design-tokens";
import { cn } from "@/lib/utils";

export type Marketplace = "ozon" | "wildberries" | "kaspi" | "custom";

export interface MarketplaceBadgeProps {
  /** Marketplace identifier */
  marketplace: Marketplace;
  /** Badge size */
  size?: "sm" | "md";
  /** Additional CSS classes */
  className?: string;
}

const MARKETPLACE_KEYS: Record<Marketplace, string> = {
  ozon: "competitors.marketplaceOzon",
  wildberries: "competitors.marketplaceWb",
  kaspi: "competitors.marketplaceKaspi",
  custom: "competitors.marketplaceCustom",
};

/**
 * Badge displaying marketplace name with brand color from design tokens.
 * Uses MARKETPLACE_COLORS: bg at 0.15 opacity, border at 0.4, text full, box-shadow glow.
 */
export function MarketplaceBadge({ marketplace, size = "md", className }: MarketplaceBadgeProps) {
  const { t } = useTranslation();
  const label = t(MARKETPLACE_KEYS[marketplace]);
  const token = MARKETPLACE_COLORS[marketplace];
  const sizeClasses = size === "sm" ? "px-1.5 py-0 text-xs" : "px-2 py-0.5 text-sm";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-medium",
        sizeClasses,
        className
      )}
      style={{
        background: `${token.bg}26`,
        borderColor: `${token.bg}66`,
        color: token.bg,
        boxShadow: `0 0 8px ${token.glow}`,
      }}
    >
      {label}
    </span>
  );
}
