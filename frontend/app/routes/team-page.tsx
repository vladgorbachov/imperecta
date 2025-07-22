import { Button } from "@/shared/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/app/providers/language-provider"

export default function Team() {
  const { t } = useLanguage()

  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold tracking-tight">{t("common", "team")}</h1>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          {t("common", "addEmployee")}
        </Button>
      </div>
      <div className="glass-card p-6">
        <p className="text-muted-foreground">Team members component will be implemented here</p>
      </div>
    </div>
  )
}
