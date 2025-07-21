"use client"

import { useState } from "react"
import { Tabs, TabsList, TabsTrigger } from "@/client/components/ui/tabs"
import { Button } from "@/client/components/ui/button"
import { Upload } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function DocumentsTabs() {
  const { t } = useLanguage()
  const [activeTab, setActiveTab] = useState("all")

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("documents", "allDocuments")}</h1>
        <p className="text-muted-foreground">{t("documents", "manageDocuments")}</p>
      </div>
      <div className="flex items-center gap-4">
        <Tabs defaultValue="all" className="w-[400px]" onValueChange={setActiveTab}>
          <TabsList>
            <TabsTrigger value="all">{t("documents", "allDocuments")}</TabsTrigger>
            <TabsTrigger value="recent">{t("documents", "recent")}</TabsTrigger>
            <TabsTrigger value="shared">{t("documents", "shared")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button>
          <Upload className="mr-2 h-4 w-4" />
          {t("documents", "uploadDocument")}
        </Button>
      </div>
    </div>
  )
}
