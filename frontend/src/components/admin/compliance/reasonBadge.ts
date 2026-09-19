import type { BlockedReason } from "@/api/admin";

/** Static key map — the i18n coverage guard forbids template-literal keys. */
export const REASON_LABELS: Record<BlockedReason, string> = {
  product_exclusion: "admin.compliance.reason.product_exclusion",
  comprehensive_sanctions: "admin.compliance.reason.comprehensive_sanctions",
  restrictive_measures: "admin.compliance.reason.restrictive_measures",
  other: "admin.compliance.reason.other",
};

export const REASON_ORDER: BlockedReason[] = [
  "product_exclusion",
  "comprehensive_sanctions",
  "restrictive_measures",
  "other",
];

/** Four distinct tones; sanctions read as the most severe. */
export const REASON_BADGE_CLASS: Record<BlockedReason, string> = {
  product_exclusion:
    "border-[var(--accent-border)] bg-[var(--accent-bg-subtle)] text-[var(--accent)]",
  comprehensive_sanctions:
    "border-[var(--status-error-border)] bg-[var(--status-error-bg)] text-[var(--status-error)]",
  restrictive_measures:
    "border-[var(--status-warn-border)] bg-[var(--status-warn-bg)] text-[var(--status-warn)]",
  other: "border-[var(--glass-border)] bg-[var(--surface-sunken-bg)] text-muted-foreground",
};
