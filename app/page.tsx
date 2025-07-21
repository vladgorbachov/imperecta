import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { AssignedToMe } from "@/client/components/dashboard/assigned-to-me"
import { ActivityStreams } from "@/client/components/dashboard/activity-streams"
import { RecentActivity } from "@/client/components/dashboard/recent-activity"
import { QuickActions } from "@/client/components/dashboard/quick-actions"


export default function HomePage() {
  return (
    <DashboardLayout>
      <div className="p-6">
        {/* Dashboard grid with custom spacing */}
        <div className="dashboard-grid">
          {/* Row 1: Main dashboard components - 3 in a row */}
          <div className="dashboard-grid-item">
            <AssignedToMe />
          </div>
          <div className="dashboard-grid-item">
            <ActivityStreams />
          </div>
          <div className="dashboard-grid-item">
            <RecentActivity />
          </div>
          
          {/* Row 2: Quick Actions - ready for more components */}
          <div className="dashboard-grid-item">
            <QuickActions />
          </div>
          {/* Add more components here - they will automatically flow to new rows */}
          {/* <div className="dashboard-grid-item">
            <NewComponent1 />
          </div> */}
          {/* <div className="dashboard-grid-item">
            <NewComponent2 />
          </div> */}
        </div>
      </div>
    </DashboardLayout>
  )
}
