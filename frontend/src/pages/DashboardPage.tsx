/**
 * Markets page. Ticker bar, Market Overview, and analytics section.
 */

import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
import { MarketsTickerBar } from "@/components/dashboard/MarketsTickerBar";
import { MarketsWidgetsSection } from "@/components/dashboard/MarketsWidgetsSection";
import { MarketDataTable } from "@/components/dashboard/MarketDataTable";
import { MarketsAnalyticsSection } from "@/components/dashboard/MarketsAnalyticsSection";

export function DashboardPage() {
  return (
    <div
      className="relative space-y-4 sm:space-y-6"
      style={{ background: "var(--gradient-accent-subtle)" }}
    >
      <PlanLimitBanner className="mb-2" />

      <MarketsTickerBar />

      <MarketsWidgetsSection />

      <div className="w-full">
        <MarketDataTable />
      </div>

      <MarketsAnalyticsSection />
    </div>
  );
}
