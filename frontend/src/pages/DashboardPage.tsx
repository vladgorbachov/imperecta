// MOBILE-2026: fully responsive + bottom nav + drawer
// Layout: KPI, MarketDataTable (left 60%) | CompetitorBenchmark, AnomalyFeed, ScenarioSimulator (right 40%)

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
    <div className="space-y-4 sm:space-y-6">
      <PageHeader title="nav.dashboard" />

      {/* Row 1: KPI Cards */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="col-span-full"
      >
        <KPIOverview />
      </motion.div>

      {/* Row 2: MarketDataTable (col-span-3, row-span-3) | Right column: Benchmark, Anomalies, Simulator */}
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
