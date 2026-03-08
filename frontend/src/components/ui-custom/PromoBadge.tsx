import { useTranslation } from "react-i18next";
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
export function PromoBadge({ type, label, className }: PromoBadgeProps) {
  const { t } = useTranslation();

  const config = {
    promo: {
      label: label ?? t("ui.promo"),
      style: {
        background: "var(--color-promo-bg)",
        border: "1px solid var(--color-promo-border)",
        color: "var(--color-promo)",
        boxShadow: "0 0 8px var(--glow-amber)",
      },
    },
    discount: {
      label: label != null ? t("ui.discount", { percent: label }) : t("ui.promo"),
      style: {
        background: "var(--color-promo-bg)",
        border: "1px solid var(--color-promo-border)",
        color: "var(--color-promo)",
        boxShadow: "0 0 8px var(--glow-amber)",
      },
    },
    out_of_stock: {
      label: label ?? t("ui.outOfStock"),
      style: {
        background: "var(--color-muted-bg)",
        border: "1px solid var(--glass-border)",
        color: "var(--color-out-of-stock)",
      },
    },
    new: {
      label: label ?? t("ui.new"),
      style: {
        background: "var(--accent-bg)",
        border: "1px solid var(--accent-border)",
        color: "var(--accent)",
        boxShadow: "0 0 8px var(--accent-glow)",
      },
    },
  }[type];

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
