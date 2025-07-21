"use client"

import { useState } from "react"
import { Tabs, TabsList, TabsTrigger } from "@/client/components/ui/tabs"
import { Button } from "@/client/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function TasksTabs() {
  const { t } = useLanguage()
  const [activeTab, setActiveTab] = useState("all")

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("tasks", "allTasks")}</h1>
        <p className="text-muted-foreground">{t("tasks", "manageTasks")}</p>
      </div>
      <div className="flex items-center gap-4">
        <Tabs defaultValue="all" className="w-[400px]" onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">{t("tasks", "allTasks")}</TabsTrigger>
            <TabsTrigger value="my">{t("tasks", "myTasks")}</TabsTrigger>
            <TabsTrigger value="team">{t("tasks", "teamTasks")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button>
          <Plus className="mr-2 h-4 w-4" />
          {t("tasks", "addTask")}
        </Button>
      </div>
    </div>
  )
}
