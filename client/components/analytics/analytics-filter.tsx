"use client"

import { useState } from "react"
import { Button } from "@/client/components/ui/button"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/client/components/ui/select"
import { Download } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function AnalyticsFilter() {
  const { t } = useLanguage()
  const [period, setPeriod] = useState("thisMonth")

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between w-full">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("analytics", "businessAnalytics")}</h1>
        <p className="text-muted-foreground">{t("analytics", "analyzeData")}</p>
      </div>
      <div className="flex items-center gap-4">
        <Select defaultValue={period} onValueChange={setPeriod}>
          <SelectTrigger className="w-[180px]">
            <SelectValue placeholder={t("analytics", "period")} />
          </SelectTrigger>
          <SelectContent>
            <SelectItem value="thisMonth">{t("analytics", "thisMonth")}</SelectItem>
            <SelectItem value="lastMonth">{t("analytics", "lastMonth")}</SelectItem>
            <SelectItem value="thisQuarter">{t("analytics", "thisQuarter")}</SelectItem>
            <SelectItem value="thisYear">{t("analytics", "thisYear")}</SelectItem>
            <SelectItem value="custom">{t("analytics", "custom")}</SelectItem>
          </SelectContent>
        </Select>
        <Button>
          <Download className="mr-2 h-4 w-4" />
          {t("analytics", "exportReport")}
        </Button>
      </div>
    </div>
  )
}
