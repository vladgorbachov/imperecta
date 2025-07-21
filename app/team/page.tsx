"use client"

import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { TeamMembers } from "@/client/components/team/team-members"
import { Button } from "@/client/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export default function TeamPage() {
  const { t } = useLanguage()

  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <div className="flex items-center justify-between">
          <h1 className="text-3xl font-bold tracking-tight">{t("common", "team")}</h1>
          <Button>
            <Plus className="mr-2 h-4 w-4" />
            {t("common", "addEmployee")}
          </Button>
        </div>
        <TeamMembers />
      </div>
    </DashboardLayout>
  )
}
