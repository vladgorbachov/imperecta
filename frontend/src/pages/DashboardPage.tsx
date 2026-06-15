/**
 * Markets page. Ticker bar, Market Overview, and analytics section.
 */

import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
import { MarketsOverviewSection } from "@/components/dashboard/MarketsOverviewSection";
import { MarketsAnalyticsSection } from "@/components/dashboard/MarketsAnalyticsSection";

export function DashboardPage() {
  return (
    <div
      className="relative space-y-4 sm:space-y-6"
      style={{ background: "var(--gradient-accent-subtle)" }}
    >
      <PlanLimitBanner className="mb-2" />

      <MarketsOverviewSection />

      <MarketsAnalyticsSection />
    </div>
  );
}
