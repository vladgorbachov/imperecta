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

const MARKETPLACE_KEYS: Record<Marketplace, string> = {
  ozon: "competitors.marketplaceOzon",
  wildberries: "competitors.marketplaceWb",
  kaspi: "competitors.marketplaceKaspi",
  custom: "competitors.marketplaceCustom",
};

const MARKETPLACE_COLOR_CLASSES: Record<Marketplace, string> = {
  ozon: "bg-marketplace-ozon/15 text-marketplace-ozon border-marketplace-ozon/30 dark:bg-marketplace-ozon/20 dark:text-marketplace-ozon dark:border-marketplace-ozon/40",
  wildberries:
    "bg-marketplace-wildberries/15 text-marketplace-wildberries border-marketplace-wildberries/30 dark:bg-marketplace-wildberries/20 dark:text-marketplace-wildberries dark:border-marketplace-wildberries/40",
  kaspi:
    "bg-marketplace-kaspi/15 text-marketplace-kaspi border-marketplace-kaspi/30 dark:bg-marketplace-kaspi/20 dark:text-marketplace-kaspi dark:border-marketplace-kaspi/40",
  custom:
    "bg-marketplace-custom/15 text-marketplace-custom border-marketplace-custom/30 dark:bg-marketplace-custom/20 dark:text-marketplace-custom dark:border-marketplace-custom/40",
};

/**
 * Badge displaying marketplace name with brand color from design tokens.
 * Ozon: blue | Wildberries: purple | Kaspi: yellow | Custom: slate
 */
export function MarketplaceBadge({ marketplace, size = "md", className }: MarketplaceBadgeProps) {
  const { t } = useTranslation();
  const label = t(MARKETPLACE_KEYS[marketplace]);
  const colorClasses = MARKETPLACE_COLOR_CLASSES[marketplace];
  const sizeClasses = size === "sm" ? "px-1.5 py-0 text-xs" : "px-2 py-0.5 text-sm";

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border font-medium",
        colorClasses,
        sizeClasses,
        className
      )}
    >
      {label}
    </span>
  );
}
