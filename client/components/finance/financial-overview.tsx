"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { LineChart } from "@/client/components/ui/charts"
import { useLanguage } from "@/client/i18n/language-context"

export function FinancialOverview() {
  const { t } = useLanguage()

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("finance", "financialOverview")}</CardTitle>
        <CardDescription>{t("finance", "manageFinances")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-4">
          <div className="grid grid-cols-3 gap-4">
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{t("finance", "income")}</p>
              <p className="text-2xl font-bold">$245,000</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{t("finance", "expenses")}</p>
              <p className="text-2xl font-bold">$145,000</p>
            </div>
            <div className="space-y-1">
              <p className="text-sm font-medium text-muted-foreground">{t("finance", "profit")}</p>
              <p className="text-2xl font-bold">$100,000</p>
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
