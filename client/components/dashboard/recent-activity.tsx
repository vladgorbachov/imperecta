"use client"

import { Activity } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { useLanguage } from "@/client/i18n/language-context"

export function RecentActivity() {
  const { t, language } = useLanguage()

  const activities = {
    en: [
      {
        id: 1,
        description: "John added a new task",
        time: "2 hours ago",
      },
      {
        id: 2,
        description: "Maria updated project status",
        time: "3 hours ago",
      },
      {
        id: 3,
        description: "New client registered",
        time: "5 hours ago",
      },
      {
        id: 4,
        description: 'Project "Website Development" completed',
        time: "1 day ago",
      },
    ],
    ru: [
      {
        id: 1,
        description: "Иван добавил новую задачу",
        time: "2 часа назад",
      },
      {
        id: 2,
        description: "Мария обновила статус проекта",
        time: "3 часа назад",
      },
      {
        id: 3,
        description: "Новый клиент зарегистрирован",
        time: "5 часов назад",
      },
      {
        id: 4,
        description: 'Завершен проект "Разработка сайта"',
        time: "1 день назад",
      },
    ],
    uk: [
      {
        id: 1,
        description: "Іван додав нове завдання",
        time: "2 години тому",
      },
      {
        id: 2,
        description: "Марія оновила статус проекту",
        time: "3 години тому",
      },
      {
        id: 3,
        description: "Новий клієнт зареєстрований",
        time: "5 годин тому",
      },
      {
        id: 4,
        description: 'Завершено проект "Розробка сайту"',
        time: "1 день тому",
      },
    ],
    ro: [
      {
        id: 1,
        description: "Ion a adăugat o sarcină nouă",
        time: "acum 2 ore",
      },
      {
        id: 2,
        description: "Maria a actualizat starea proiectului",
        time: "acum 3 ore",
      },
      {
        id: 3,
        description: "Client nou înregistrat",
        time: "acum 5 ore",
      },
      {
        id: 4,
        description: 'Proiectul "Dezvoltare site web" finalizat',
        time: "acum 1 zi",
      },
    ],
  }

  const currentActivities = activities[language]

  return (
    <Card className="h-full">
      <CardHeader className="pb-3">
        <CardTitle>{t("dashboard", "recentActivity")}</CardTitle>
        <CardDescription>{t("dashboard", "recentActivityDesc")}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4 overflow-y-auto max-h-96">
          {currentActivities.map((activity) => (
            <div key={activity.id} className="flex items-start gap-4">
              <div className="rounded-full bg-primary/10 p-2">
                <Activity className="h-4 w-4 text-primary" />
              </div>
              <div className="space-y-1">
                <p className="text-sm font-medium leading-none">{activity.description}</p>
                <p className="text-sm text-muted-foreground">{activity.time}</p>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
