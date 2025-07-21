"use client"

import { Plus, FileText, Users, Calendar, MessageSquare } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Button } from "@/client/components/ui/button"
import { useLanguage } from "@/client/i18n/language-context"

export function QuickActions() {
  const { t } = useLanguage()

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>{t("dashboard", "quickActions")}</CardTitle>
        <CardDescription>{t("dashboard", "quickActionsDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-2">
          <Button className="w-full justify-start">
            <Plus className="mr-2 h-4 w-4" />
            {t("common", "newProject")}
          </Button>
          <Button className="w-full justify-start" variant="outline">
            <FileText className="mr-2 h-4 w-4" />
            {t("dashboard", "createReport")}
          </Button>
          <Button className="w-full justify-start" variant="outline">
            <Users className="mr-2 h-4 w-4" />
            {t("dashboard", "manageTeam")}
          </Button>
          <Button className="w-full justify-start" variant="outline">
            <Calendar className="mr-2 h-4 w-4" />
            {t("dashboard", "scheduleMeeting")}
          </Button>
          <Button className="w-full justify-start" variant="outline">
            <MessageSquare className="mr-2 h-4 w-4" />
            {t("dashboard", "sendMessage")}
          </Button>
        </div>
      </CardContent>
    </Card>
  )
}
