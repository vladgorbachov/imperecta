import { ProjectsList } from "@/shared/components/projects/projects-list"
import { Button } from "@/shared/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/app/providers/language-provider"

export default function Projects() {
  const { t } = useLanguage()

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight dark:gradient-text">{t("common", "projects")}</h1>
        <Button className="dark:neon-glow">
          <Plus className="mr-2 h-4 w-4" />
          {t("common", "newProject")}
        </Button>
      </div>
      <div className="page-grid">
        <div className="page-grid-item col-span-full">
          <ProjectsList />
        </div>
      </div>
    </div>
  )
}
