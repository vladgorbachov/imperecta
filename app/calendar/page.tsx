import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { CalendarView } from "@/client/components/calendar/calendar-view"
import { CalendarHeader } from "@/client/components/calendar/calendar-header"

export default function CalendarPage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <CalendarHeader />
        <CalendarView />
      </div>
    </DashboardLayout>
  )
}
