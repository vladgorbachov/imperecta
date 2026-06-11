import { useTranslation } from "react-i18next";
import type { TFunction } from "i18next";
import { cn } from "@/lib/utils";

export type PromoType = "promo" | "discount" | "out_of_stock" | "new";

export interface PromoBadgeProps {
  /** Badge type determining color and default label */
  type: PromoType;
  /** Optional custom label (overrides default for discount: pass percent e.g. "15") */
  label?: string;
  /** Additional CSS classes */
  className?: string;
}

/**
 * Badge for product promo states: promo/discount (amber glow), out_of_stock (muted), new (accent).
 */
type PromoConfig = { label: string; style: object };

function getPromoConfig(type: PromoType, label: string | undefined, t: TFunction): PromoConfig {
  switch (type) {
    case "promo":
      return {
        label: label ?? t("ui.promo"),
        style: {
          background: "var(--color-promo-bg)",
          border: "1px solid var(--color-promo-border)",
          color: "var(--color-promo)",
          boxShadow: "0 0 8px var(--glow-amber)",
        },
      };
    case "discount":
      return {
        label: label != null ? t("ui.discount", { percent: label }) : t("ui.promo"),
        style: {
          background: "var(--color-promo-bg)",
          border: "1px solid var(--color-promo-border)",
          color: "var(--color-promo)",
          boxShadow: "0 0 8px var(--glow-amber)",
        },
      };
    case "out_of_stock":
      return {
        label: label ?? t("ui.outOfStock"),
        style: {
          background: "var(--color-muted-bg)",
          border: "1px solid var(--glass-border)",
          color: "var(--color-out-of-stock)",
        },
      };
    case "new":
      return {
        label: label ?? t("ui.new"),
        style: {
          background: "var(--accent-bg)",
          border: "1px solid var(--accent-border)",
          color: "var(--accent)",
          boxShadow: "0 0 8px var(--accent-glow)",
        },
      };
  }
}

export function PromoBadge({ type, label, className }: PromoBadgeProps) {
  const { t } = useTranslation();
  const config = getPromoConfig(type, label, t);

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        className
      )}
      style={config.style}
    >
      {config.label}
    </span>
  );
}
