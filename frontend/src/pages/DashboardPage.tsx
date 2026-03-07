/**
 * AI Market Command Center dashboard.
 * Responsive grid layout with KPI, charts, anomalies, benchmark, simulator, AI panel, quick actions.
 */

import { motion } from "framer-motion";
import { KPIOverview } from "@/components/dashboard/KPIOverview";
import { PriceTrendChart } from "@/components/dashboard/PriceTrendChart";
import { AnomalyFeed } from "@/components/dashboard/AnomalyFeed";
import { CompetitorBenchmark } from "@/components/dashboard/CompetitorBenchmark";
import { ScenarioSimulator } from "@/components/dashboard/ScenarioSimulator";
import { AIInsightsPanel } from "@/components/dashboard/AIInsightsPanel";
import { QuickActions } from "@/components/dashboard/QuickActions";
import { PageHeader } from "@/components/ui-custom/PageHeader";

export function DashboardPage() {
  return (
    <div className="space-y-6">
      <PageHeader title="nav.dashboard" />

      {/* Row 1: KPI Overview */}
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        transition={{ duration: 0.3 }}
        className="col-span-full"
      >
        <KPIOverview />
      </motion.div>

      {/* Row 2: PriceTrendChart + AnomalyFeed */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <PriceTrendChart />
        </div>
        <div className="lg:col-span-2">
          <AnomalyFeed />
        </div>
      </div>

      {/* Row 3: ScenarioSimulator + CompetitorBenchmark */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <ScenarioSimulator />
        </div>
        <div className="lg:col-span-2">
          <CompetitorBenchmark />
        </div>
      </div>

      {/* Row 4: AIInsightsPanel + QuickActions */}
      <div className="grid grid-cols-1 gap-4 lg:grid-cols-5">
        <div className="lg:col-span-3">
          <AIInsightsPanel />
        </div>
        <div className="lg:col-span-2">
          <QuickActions />
        </div>
      </div>
    </div>
  );
}
