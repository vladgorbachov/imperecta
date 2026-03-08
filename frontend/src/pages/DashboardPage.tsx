// MOBILE-2026: fully responsive + bottom nav + drawer
// Bloomberg-style layout: KPI, MarketDataTable, CompetitorBenchmark, AnomalyFeed, ScenarioSimulator

/**
 * AI Market Command Center dashboard.
 * Bloomberg-style: KPI, MarketDataTable, CompetitorBenchmark, AnomalyFeed, ScenarioSimulator.
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

      {/* Row 2: MarketDataTable (60%) | CompetitorBenchmark + AnomalyFeed (40%) */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="min-w-0 lg:col-span-3">
          <MarketDataTable />
        </div>
        <div className="flex min-w-0 flex-col gap-4 lg:col-span-2">
          <CompetitorBenchmark />
          <AnomalyFeed />
        </div>
      </div>

      {/* Row 3: ScenarioSimulator (full width) */}
      <div className="min-w-0">
        <ScenarioSimulator />
      </div>
    </div>
  );
}
