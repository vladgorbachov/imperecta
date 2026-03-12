import { useTranslation } from "react-i18next";
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

/**
 * Badge displaying marketplace name with brand color from design tokens.
 * Uses MARKETPLACE_COLORS: bg at 0.15 opacity, border at 0.4, text full, box-shadow glow.
 */
function getMarketplaceLabel(m: Marketplace): string {
  switch (m) {
    case "ozon":
      return "competitors.marketplaceOzon";
    case "wildberries":
      return "competitors.marketplaceWb";
    case "kaspi":
      return "competitors.marketplaceKaspi";
    case "custom":
      return "competitors.marketplaceCustom";
  }
}

function getMarketplaceToken(m: Marketplace): { bg: string; glow: string } {
  switch (m) {
    case "ozon":
      return { bg: "#005BFF", glow: "rgba(0,91,255,0.3)" };
    case "wildberries":
      return { bg: "#CB11AB", glow: "rgba(203,17,171,0.3)" };
    case "kaspi":
      return { bg: "#F14635", glow: "rgba(241,70,53,0.3)" };
    case "custom":
      return { bg: "#64748b", glow: "rgba(100,116,139,0.3)" };
  }
}

export function MarketplaceBadge({ marketplace, size = "md", className }: MarketplaceBadgeProps) {
  const { t } = useTranslation();
  const label = t(getMarketplaceLabel(marketplace));
  const token = getMarketplaceToken(marketplace);
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
