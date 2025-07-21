"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { LineChart } from "@/client/components/ui/charts"
import { useLanguage } from "@/client/i18n/language-context"

export function DashboardOverview() {
  const { t } = useLanguage()

  return (
    <Card className="col-span-2">
      <CardHeader>
        <CardTitle>{t("dashboard", "businessOverview")}</CardTitle>
        <CardDescription>{t("dashboard", "keyPerformanceIndicators")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4">
          <div className="grid grid-cols-2 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{t("dashboard", "revenue")}</p>
              <p className="text-2xl font-bold">$1,245,000</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{t("dashboard", "expenses")}</p>
              <p className="text-2xl font-bold">$845,000</p>
            </div>
          </div>
          <div className="h-[200px]">
            <LineChart />
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
