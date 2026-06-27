import type { ServiceAlertSeverity } from "@/api/admin";

export interface SeverityStyle {
  borderClass: string;
  badgeClass: string;
  labelKey: string;
}

/** Severity → project token mapping for borders and badges. */
export const SEVERITY_STYLES: Record<ServiceAlertSeverity, SeverityStyle> = {
  info: {
    borderClass: "border-l-[var(--accent)]",
    badgeClass:
      "border border-[var(--accent-border)] bg-[var(--accent-bg)] text-[var(--accent-bright)]",
    labelKey: "admin.alerts.severity.info",
  },
  warning: {
    borderClass: "border-l-[var(--color-promo)]",
    badgeClass:
      "border border-[var(--color-promo-border)] bg-[var(--color-promo-bg)] text-[var(--color-promo)]",
    labelKey: "admin.alerts.severity.warning",
  },
  error: {
    borderClass: "border-l-[var(--color-price-up)]",
    badgeClass:
      "border border-[var(--color-price-up-border)] bg-[var(--color-price-up-bg)] text-[var(--color-price-up)]",
    labelKey: "admin.alerts.severity.error",
  },
  critical: {
    borderClass: "border-l-[var(--color-price-up)]",
    badgeClass:
      "border border-[var(--color-price-up-border)] bg-[var(--color-price-up-bg)] text-[var(--color-price-up)] shadow-[0_0_8px_var(--glow-red)]",
    labelKey: "admin.alerts.severity.critical",
  },
};

export function isServiceAlertSeverity(value: string): value is ServiceAlertSeverity {
  return value === "info" || value === "warning" || value === "error" || value === "critical";
}
