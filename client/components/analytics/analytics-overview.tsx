"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { LineChart } from "@/client/components/ui/charts"
import { useLanguage } from "@/client/i18n/language-context"

export function AnalyticsOverview() {
  const { t } = useLanguage()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("analytics", "salesOverview")}</CardTitle>
        <CardDescription>{t("analytics", "revenueByMonth")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="h-[300px]">
          <LineChart />
        </div>
      </CardContent>
    </Card>
  )
}
