import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { AssignedToMe } from "@/client/components/dashboard/assigned-to-me"
import { ActivityStreams } from "@/client/components/dashboard/activity-streams"
import { RecentActivity } from "@/client/components/dashboard/recent-activity"
import { QuickActions } from "@/client/components/dashboard/quick-actions"

export default function HomePage() {
  return (
    <DashboardLayout>
      <div className="space-y-6">
        {/* Welcome Section */}
        <div className="glass-card">
          <div className="flex items-center justify-between">
            <div>
              <h1 className="text-3xl font-bold bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent">
                Welcome to Imperecta
              </h1>
              <p className="text-muted-foreground mt-2">
                Your modern enterprise management dashboard with glass morphism design
              </p>
            </div>
            <div className="hidden md:flex items-center gap-2">
              <div className="w-3 h-3 rounded-full bg-green-500 animate-pulse" />
              <span className="text-sm text-muted-foreground">System Online</span>
            </div>
          </div>
        </div>

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
    </DashboardLayout>
  )
}
