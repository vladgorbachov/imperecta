/**
 * Markets page. Ticker bar and Market Overview (KPI, movers, coverage, news, catalog).
 */

import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
import { MarketsOverviewSection } from "@/components/dashboard/MarketsOverviewSection";

export function DashboardPage() {
  return (
    <div
      className="relative space-y-4 sm:space-y-6"
      style={{ background: "var(--gradient-accent-subtle)" }}
    >
      <PlanLimitBanner className="mb-2" />

      <MarketsOverviewSection />
    </div>
  );
}
