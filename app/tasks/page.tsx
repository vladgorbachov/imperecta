import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { TasksList } from "@/client/components/tasks/tasks-list"
import { TasksTabs } from "@/client/components/tasks/tasks-tabs"

export default function TasksPage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <TasksTabs />
        <TasksList />
      </div>
    </DashboardLayout>
  )
}
