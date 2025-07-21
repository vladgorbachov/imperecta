import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { DocumentsExplorer } from "@/client/components/documents/documents-explorer"
import { DocumentsTabs } from "@/client/components/documents/documents-tabs"

export default function DocumentsPage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <DocumentsTabs />
        <DocumentsExplorer />
      </div>
    </DashboardLayout>
  )
}
