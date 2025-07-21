"use client"

import { User, FileText, MessageSquare, GitPullRequest, Clock } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { useLanguage } from "@/client/i18n/language-context"

export function ActivityStreams() {
  const { t, language } = useLanguage()

  const activities = {
    en: [
      {
        id: 1,
        user: "Alex Smith",
        action: "commented on",
        item: "API Documentation",
        time: "10 minutes ago",
        type: "comment",
      },
      {
        id: 2,
        user: "Maria Johnson",
        action: "created",
        item: "New Feature Request",
        time: "1 hour ago",
        type: "task",
      },
      {
        id: 3,
        user: "John Doe",
        action: "submitted",
        item: "Pull Request #42",
        time: "2 hours ago",
        type: "code",
      },
      {
        id: 4,
        user: "Emily Wilson",
        action: "updated",
        item: "Project Timeline",
        time: "Yesterday",
        type: "update",
      },
    ],
    ru: [
      {
        id: 1,
        user: "Алексей Смирнов",
        action: "прокомментировал",
        item: "Документацию API",
        time: "10 минут назад",
        type: "comment",
      },
      {
        id: 2,
        user: "Мария Иванова",
        action: "создала",
        item: "Запрос на новую функцию",
        time: "1 час назад",
        type: "task",
      },
      {
        id: 3,
        user: "Иван Петров",
        action: "отправил",
        item: "Запрос на слияние #42",
        time: "2 часа назад",
        type: "code",
      },
      {
        id: 4,
        user: "Елена Сидорова",
        action: "обновила",
        item: "График проекта",
        time: "Вчера",
        type: "update",
      },
    ],
    uk: [
      {
        id: 1,
        user: "Олексій Смирнов",
        action: "прокоментував",
        item: "Документацію API",
        time: "10 хвилин тому",
        type: "comment",
      },
      {
        id: 2,
        user: "Марія Іванова",
        action: "створила",
        item: "Запит на нову функцію",
        time: "1 годину тому",
        type: "task",
      },
      {
        id: 3,
        user: "Іван Петров",
        action: "надіслав",
        item: "Запит на злиття #42",
        time: "2 години тому",
        type: "code",
      },
      {
        id: 4,
        user: "Олена Сидорова",
        action: "оновила",
        item: "Графік проекту",
        time: "Вчора",
        type: "update",
      },
    ],
    ro: [
      {
        id: 1,
        user: "Alex Popescu",
        action: "a comentat pe",
        item: "Documentația API",
        time: "acum 10 minute",
        type: "comment",
      },
      {
        id: 2,
        user: "Maria Ionescu",
        action: "a creat",
        item: "Cerere de funcționalitate nouă",
        time: "acum 1 oră",
        type: "task",
      },
      {
        id: 3,
        user: "Ion Popa",
        action: "a trimis",
        item: "Cerere de pull #42",
        time: "acum 2 ore",
        type: "code",
      },
      {
        id: 4,
        user: "Elena Dumitru",
        action: "a actualizat",
        item: "Cronologia proiectului",
        time: "Ieri",
        type: "update",
      },
    ],
  }

  const currentActivities = activities[language]

  const getActivityIcon = (type: string) => {
    switch (type) {
      case "comment":
        return <MessageSquare className="h-4 w-4 text-blue-500" />
      case "task":
        return <FileText className="h-4 w-4 text-green-500" />
      case "code":
        return <GitPullRequest className="h-4 w-4 text-purple-500" />
      case "update":
        return <Clock className="h-4 w-4 text-yellow-500" />
      default:
        return <User className="h-4 w-4 text-gray-500" />
    }
  }

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="flex items-center gap-2 text-xl font-bold bg-gradient-to-r from-purple-600 to-cyan-600 bg-clip-text text-transparent">
          <div className="w-2 h-2 rounded-full bg-gradient-to-r from-purple-500 to-cyan-600 animate-pulse" />
          Activity Streams
        </CardTitle>
        <CardDescription className="text-muted-foreground">
          Recent activity across your projects
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-3 overflow-y-auto max-h-96 pr-2">
          {currentActivities.map((activity, index) => (
            <div 
              key={activity.id} 
              className="glass rounded-xl p-4 hover:scale-105 transition-all duration-300 cursor-pointer group"
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="flex items-start gap-3">
                <div className="mt-1 p-2 rounded-full bg-muted/50 group-hover:bg-primary/10 transition-colors">
                  {getActivityIcon(activity.type)}
                </div>
                <div className="space-y-2 flex-1">
                  <p className="font-medium leading-tight">
                    <span className="text-primary font-semibold hover:text-primary/80 transition-colors">
                      {activity.user}
                    </span>{" "}
                    <span className="text-muted-foreground">{activity.action}</span>{" "}
                    <span className="font-semibold text-foreground group-hover:text-primary transition-colors">
                      {activity.item}
                    </span>
                  </p>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground bg-muted/30 px-2 py-1 rounded-full">
                      {activity.time}
                    </span>
                    <div className={`
                      w-2 h-2 rounded-full
                      ${activity.type === 'comment' ? 'bg-blue-500' :
                        activity.type === 'task' ? 'bg-green-500' :
                        activity.type === 'code' ? 'bg-purple-500' :
                        'bg-yellow-500'}
                    `} />
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
