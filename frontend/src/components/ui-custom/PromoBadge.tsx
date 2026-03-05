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
 * Badge for product promo states: promo (amber), discount (amber), out_of_stock (grey), new (teal).
 */
export function PromoBadge({ type, label, className }: PromoBadgeProps) {
  const { t } = useTranslation();

  const config = {
    promo: {
      label: label ?? t("ui.promo"),
      classes:
        "bg-promo/15 text-promo border-promo/30 dark:bg-promo/20 dark:text-promo dark:border-promo/40",
    },
    discount: {
      label: label != null ? t("ui.discount", { percent: label }) : t("ui.promo"),
      classes:
        "bg-promo/15 text-promo border-promo/30 dark:bg-promo/20 dark:text-promo dark:border-promo/40",
    },
    out_of_stock: {
      label: label ?? t("ui.outOfStock"),
      classes:
        "bg-out-of-stock/15 text-out-of-stock border-out-of-stock/30 dark:bg-out-of-stock/20 dark:text-out-of-stock dark:border-out-of-stock/40",
    },
    new: {
      label: label ?? t("ui.new"),
      classes:
        "bg-primary/15 text-primary border-primary/30 dark:bg-primary/20 dark:text-primary dark:border-primary/40",
    },
  }[type];

  return (
    <span
      className={cn(
        "inline-flex items-center rounded-md border px-2 py-0.5 text-xs font-medium",
        config.classes,
        className
      )}
    >
      {config.label}
    </span>
  );
}
