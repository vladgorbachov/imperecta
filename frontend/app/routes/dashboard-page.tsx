import { AssignedToMe } from "@/widgets/dashboard/assigned-to-me"
import { ActivityStreams } from "@/widgets/dashboard/activity-streams"
import { RecentActivity } from "@/widgets/dashboard/recent-activity"
import { QuickActions } from "@/widgets/dashboard/quick-actions"

export default function DashboardPage() {
  return (
    <div className="space-y-6">
      {/* Dashboard grid with glass spacing */}
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
        
        {/* Row 2: Quick Actions - spans full width */}
        <div className="dashboard-grid-item col-span-full lg:col-span-1">
          <QuickActions />
        </div>
        
        {/* Future components will automatically flow to new rows */}
        {/* <div className="dashboard-grid-item">
          <NewComponent1 />
        </div> */}
        {/* <div className="dashboard-grid-item">
          <NewComponent2 />
        </div> */}
      </div>
    </div>
  )
}
