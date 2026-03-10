/**
 * Banner shown when Free plan user is at or over product limit.
 * Displays upgrade messaging without aggressive tone.
 */

import { useTranslation } from "react-i18next";
import { Zap } from "lucide-react";
import { usePlanLimits } from "@/hooks/usePlanLimits";
import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

interface PlanLimitBannerProps {
  className?: string;
}

export function PlanLimitBanner({ className }: PlanLimitBannerProps) {
  const { t } = useTranslation();
  const { totalProducts, productLimit, isAtOrOverProductLimit } = usePlanLimits();

  if (!isAtOrOverProductLimit) return null;

  const isOver = totalProducts > productLimit;

  return (
    <div
      className={cn(
        "flex flex-wrap items-center justify-between gap-3 rounded-lg border px-4 py-3",
        isOver
          ? "border-amber-500/50 bg-amber-500/10 dark:border-amber-400/30 dark:bg-amber-500/5"
          : "border-[var(--color-promo-border)] bg-[var(--color-promo-bg)] dark:border-amber-400/20 dark:bg-amber-500/5",
        className
      )}
    >
      <p className="text-sm font-medium" style={{ color: "var(--color-promo)" }}>
        {isOver
          ? t("planLimit.overLimit", { current: totalProducts, limit: productLimit })
          : t("planLimit.atLimit", { limit: productLimit })}
      </p>
      <Button
        size="sm"
        className="shrink-0"
        disabled
        style={{
          background: "linear-gradient(135deg, var(--accent-dim), var(--accent))",
          border: "none",
          color: "var(--primary-foreground)",
        }}
      >
        <Zap className="mr-2 size-4" />
        {t("settings.upgradeComingSoon")}
      </Button>
    </div>
  );
}
