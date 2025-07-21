import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { ProjectsList } from "@/client/components/projects/projects-list"
import { Button } from "@/client/components/ui/button"
import { Plus } from "lucide-react"

export default function ProjectsPage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">Проекты</h1>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            Новый проект
          </Button>
        </div>
        <ProjectsList />
      </div>
    </DashboardLayout>
  )
}
