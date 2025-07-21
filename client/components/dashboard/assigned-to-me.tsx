"use client"

import { CheckCircle, Clock, AlertCircle } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { useLanguage } from "@/client/i18n/language-context"
import type { JSX } from "react"

export function AssignedToMe() {
  const { t, language } = useLanguage()

  const tasks = {
    en: [
      {
        id: 1,
        title: "Implement user authentication",
        project: "Website Redesign",
        priority: "High",
        status: "In Progress",
        dueDate: "Tomorrow",
      },
      {
        id: 2,
        title: "Fix responsive layout issues",
        project: "Mobile App",
        priority: "Medium",
        status: "To Do",
        dueDate: "Friday",
      },
      {
        id: 3,
        title: "Create API documentation",
        project: "Backend Services",
        priority: "Low",
        status: "In Review",
        dueDate: "Next week",
      },
      {
        id: 4,
        title: "Update dependencies",
        project: "DevOps",
        priority: "Medium",
        status: "In Progress",
        dueDate: "Today",
      },
    ],
    ru: [
      {
        id: 1,
        title: "Внедрить аутентификацию пользователей",
        project: "Редизайн сайта",
        priority: "Высокий",
        status: "В процессе",
        dueDate: "Завтра",
      },
      {
        id: 2,
        title: "Исправить проблемы с адаптивной версткой",
        project: "Мобильное приложение",
        priority: "Средний",
        status: "К выполнению",
        dueDate: "Пятница",
      },
      {
        id: 3,
        title: "Создать документацию API",
        project: "Бэкенд сервисы",
        priority: "Низкий",
        status: "На проверке",
        dueDate: "Следующая неделя",
      },
      {
        id: 4,
        title: "Обновить зависимости",
        project: "DevOps",
        priority: "Средний",
        status: "В процессе",
        dueDate: "Сегодня",
      },
    ],
    uk: [
      {
        id: 1,
        title: "Впровадити аутентифікацію користувачів",
        project: "Редизайн сайту",
        priority: "Високий",
        status: "В процесі",
        dueDate: "Завтра",
      },
      {
        id: 2,
        title: "Виправити проблеми з адаптивною версткою",
        project: "Мобільний додаток",
        priority: "Середній",
        status: "До виконання",
        dueDate: "П'ятниця",
      },
      {
        id: 3,
        title: "Створити документацію API",
        project: "Бекенд сервіси",
        priority: "Низький",
        status: "На перевірці",
        dueDate: "Наступний тиждень",
      },
      {
        id: 4,
        title: "Оновити залежності",
        project: "DevOps",
        priority: "Середній",
        status: "В процесі",
        dueDate: "Сьогодні",
      },
    ],
    ro: [
      {
        id: 1,
        title: "Implementare autentificare utilizator",
        project: "Redesign site web",
        priority: "Ridicată",
        status: "În desfășurare",
        dueDate: "Mâine",
      },
      {
        id: 2,
        title: "Rezolvare probleme layout responsiv",
        project: "Aplicație mobilă",
        priority: "Medie",
        status: "De făcut",
        dueDate: "Vineri",
      },
      {
        id: 3,
        title: "Creare documentație API",
        project: "Servicii backend",
        priority: "Scăzută",
        status: "În revizuire",
        dueDate: "Săptămâna viitoare",
      },
      {
        id: 4,
        title: "Actualizare dependențe",
        project: "DevOps",
        priority: "Medie",
        status: "În desfășurare",
        dueDate: "Astăzi",
      },
    ],
  }

  const currentTasks = tasks[language]

  const getStatusIcon = (status: string) => {
    const statusMap: Record<string, JSX.Element> = {
      "In Progress": <Clock className="h-4 w-4 text-blue-500" />,
      "To Do": <AlertCircle className="h-4 w-4 text-yellow-500" />,
      "In Review": <CheckCircle className="h-4 w-4 text-green-500" />,
      "В процессе": <Clock className="h-4 w-4 text-blue-500" />,
      "К выполнению": <AlertCircle className="h-4 w-4 text-yellow-500" />,
      "На проверке": <CheckCircle className="h-4 w-4 text-green-500" />,
      "В процесі": <Clock className="h-4 w-4 text-blue-500" />,
      "До виконання": <AlertCircle className="h-4 w-4 text-yellow-500" />,
      "На перевірці": <CheckCircle className="h-4 w-4 text-green-500" />,
      "În desfășurare": <Clock className="h-4 w-4 text-blue-500" />,
      "De făcut": <AlertCircle className="h-4 w-4 text-yellow-500" />,
      "În revizuire": <CheckCircle className="h-4 w-4 text-green-500" />,
    }
    return statusMap[status] || <AlertCircle className="h-4 w-4 text-gray-500" />
  }

  return (
    <Card className="h-full">
      <CardHeader>
        <CardTitle>Assigned to Me</CardTitle>
        <CardDescription>Tasks that require your attention</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="space-y-4 overflow-y-auto max-h-96">
          {currentTasks.map((task) => (
            <div key={task.id} className="flex items-start gap-4 rounded-md border p-3 hover:bg-muted/50">
              <div className="mt-0.5">{getStatusIcon(task.status)}</div>
              <div className="space-y-1">
                <p className="font-medium leading-none">{task.title}</p>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <span>{task.project}</span>
                  <span>•</span>
                  <span>{task.dueDate}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
