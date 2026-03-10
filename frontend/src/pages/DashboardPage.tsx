/**
 * AI Market Command Center dashboard.
 * Grid: MarketDataTable spans full left column; right column: Benchmark, Anomalies, Simulator.
 */

import { motion } from "framer-motion";
import { KPIOverview } from "@/components/dashboard/KPIOverview";
import { MarketDataTable } from "@/components/dashboard/MarketDataTable";
import { PlanLimitBanner } from "@/components/ui-custom/PlanLimitBanner";
import { AnomalyFeed } from "@/components/dashboard/AnomalyFeed";
import { CompetitorBenchmark } from "@/components/dashboard/CompetitorBenchmark";
import { ScenarioSimulator } from "@/components/dashboard/ScenarioSimulator";
import { PageHeader } from "@/components/ui-custom/PageHeader";

export function DashboardPage() {
  return (
    <div
      className="relative space-y-4 sm:space-y-6"
      style={{ background: "var(--gradient-accent-subtle)" }}
    >
      <PlanLimitBanner className="mb-2" />
      <PageHeader title="nav.dashboard" />

      {/* Row 1: KPI Cards with stagger */}
      <div className="col-span-full">
        <KPIOverview />
      </div>

      {/* Row 2: Market Overview — full width primary block */}
      <div className="w-full">
        <MarketDataTable />
      </div>

      {/* Row 3: Competitor Benchmark, Anomalies, What If — below Market Overview */}
      <div className="grid grid-cols-1 gap-4 md:grid-cols-2 lg:grid-cols-3">
        <div className="min-w-0 max-h-[320px] overflow-y-auto">
          <CompetitorBenchmark />
        </div>
        <div className="min-w-0 max-h-[320px] overflow-y-auto">
          <AnomalyFeed />
        </div>
        <div className="min-w-0 md:col-span-2 lg:col-span-1">
          <ScenarioSimulator />
        </div>
      </div>
    </div>
  );
}
