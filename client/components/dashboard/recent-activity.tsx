"use client"

import { Activity, Clock, CheckCircle, UserPlus, Trophy } from "lucide-react"
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
        type: "task",
      },
      {
        id: 2,
        description: "Maria updated project status",
        time: "3 hours ago",
        type: "update",
      },
      {
        id: 3,
        description: "New client registered",
        time: "5 hours ago",
        type: "user",
      },
      {
        id: 4,
        description: 'Project "Website Development" completed',
        time: "1 day ago",
        type: "complete",
      },
    ],
    ru: [
      {
        id: 1,
        description: "Иван добавил новую задачу",
        time: "2 часа назад",
        type: "task",
      },
      {
        id: 2,
        description: "Мария обновила статус проекта",
        time: "3 часа назад",
        type: "update",
      },
      {
        id: 3,
        description: "Новый клиент зарегистрирован",
        time: "5 часов назад",
        type: "user",
      },
      {
        id: 4,
        description: 'Завершен проект "Разработка сайта"',
        time: "1 день назад",
        type: "complete",
      },
    ],
    uk: [
      {
        id: 1,
        description: "Іван додав нове завдання",
        time: "2 години тому",
        type: "task",
      },
      {
        id: 2,
        description: "Марія оновила статус проекту",
        time: "3 години тому",
        type: "update",
      },
      {
        id: 3,
        description: "Новий клієнт зареєстрований",
        time: "5 годин тому",
        type: "user",
      },
      {
        id: 4,
        description: 'Завершено проект "Розробка сайту"',
        time: "1 день тому",
        type: "complete",
      },
    ],
    ro: [
      {
        id: 1,
        description: "Ion a adăugat o sarcină nouă",
        time: "acum 2 ore",
        type: "task",
      },
      {
        id: 2,
        description: "Maria a actualizat starea proiectului",
        time: "acum 3 ore",
        type: "update",
      },
      {
        id: 3,
        description: "Client nou înregistrat",
        time: "acum 5 ore",
        type: "user",
      },
      {
        id: 4,
        description: 'Proiectul "Dezvoltare site web" finalizat',
        time: "acum 1 zi",
        type: "complete",
      },
    ],
  }

  const currentActivities = activities[language]

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "task":
        return <Activity className="h-4 w-4 text-blue-500" />
      case "update":
        return <Clock className="h-4 w-4 text-yellow-500" />
      case "user":
        return <UserPlus className="h-4 w-4 text-green-500" />
      case "complete":
        return <Trophy className="h-4 w-4 text-purple-500" />
      default:
        return <Activity className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="text-xl font-bold bg-gradient-to-r from-cyan-600 to-blue-600 bg-clip-text text-transparent">
          {t("dashboard", "recentActivity")}
        </CardTitle>
        <CardDescription className="text-muted-foreground">
          {t("dashboard", "recentActivityDesc")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 overflow-y-auto max-h-96 pr-2">
          {currentActivities.map((activity, index) => (
            <div 
              key={activity.id} 
              className="glass rounded-xl p-4 hover:scale-105 transition-all duration-300 cursor-pointer group"
              style={{ animationDelay: `${index * 150}ms` }}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1 p-2 rounded-full bg-muted/50 group-hover:bg-primary/10 transition-colors">
                  {getActivityIcon(activity.type)}
                </div>
                <div className="space-y-2 flex-1">
                  <p className="font-medium leading-tight text-foreground group-hover:text-primary transition-colors">
                    {activity.description}
                  </p>
                                     <div className="flex items-center gap-2">
                     <span className="text-xs text-muted-foreground bg-muted/30 px-2 py-1 rounded-full">
                       {activity.time}
                     </span>
                   </div>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
