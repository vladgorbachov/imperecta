"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { BarChart } from "@/client/components/ui/charts"
import { useLanguage } from "@/client/i18n/language-context"

export function AnalyticsCharts() {
  const { t } = useLanguage()

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
      <Card>
        <CardHeader>
          <CardTitle>{t("analytics", "topClients")}</CardTitle>
          <CardDescription>{t("analytics", "revenueByMonth")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <BarChart />
          </div>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>{t("analytics", "teamPerformance")}</CardTitle>
          <CardDescription>{t("analytics", "revenueByMonth")}</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="h-[300px]">
            <BarChart />
          </div>
        </CardContent>
      </Card>
    </div>
  )
}
