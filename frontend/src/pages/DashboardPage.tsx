/**
 * AI Market Command Center dashboard.
 * Grid: MarketDataTable spans full left column; right column: Benchmark, Anomalies, Simulator.
 */

import { motion } from "framer-motion";
import { KPIOverview } from "@/components/dashboard/KPIOverview";
import { MarketDataTable } from "@/components/dashboard/MarketDataTable";
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
      <PageHeader title="nav.dashboard" />

      {/* Row 1: KPI Cards with stagger */}
      <div className="col-span-full">
        <KPIOverview />
      </div>

      {/* Row 2: MarketDataTable | Right column */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="flex min-w-0 flex-col lg:col-span-3 lg:row-span-3">
          <MarketDataTable />
        </div>
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <div className="max-h-[300px] overflow-y-auto">
            <CompetitorBenchmark />
          </div>
          <div className="max-h-[200px] overflow-y-auto">
            <AnomalyFeed />
          </div>
          <div className="max-h-[150px] shrink-0">
            <ScenarioSimulator />
          </div>
        </div>
      </div>
    </div>
  );
}
