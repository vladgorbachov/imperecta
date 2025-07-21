import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { AnalyticsOverview } from "@/client/components/analytics/analytics-overview"
import { AnalyticsCharts } from "@/client/components/analytics/analytics-charts"
import { AnalyticsFilter } from "@/client/components/analytics/analytics-filter"

export default function AnalyticsPage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
          <AnalyticsFilter />
        </div>
        <AnalyticsOverview />
        <AnalyticsCharts />
      </div>
    </DashboardLayout>
  )
}
