"use client"
import { Card, CardContent } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { Badge } from "@/client/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/client/components/ui/dropdown-menu"
import { Button } from "@/client/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { MoreHorizontal } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function TasksList() {
  const { t, language } = useLanguage()

  const tasks = {
    en: [
      {
        id: 1,
        title: "Design new landing page",
        assignedTo: "Maria Johnson",
        priority: "High",
        dueDate: "2023-05-15",
        status: "In Progress",
      },
      {
        id: 2,
        title: "Fix login issues",
        assignedTo: "Alex Smith",
        priority: "High",
        dueDate: "2023-05-10",
        status: "To Do",
      },
      {
        id: 3,
        title: "Update documentation",
        assignedTo: "John Doe",
        priority: "Medium",
        dueDate: "2023-05-20",
        status: "Review",
      },
      {
        id: 4,
        title: "Implement payment gateway",
        assignedTo: "Emily Wilson",
        priority: "High",
        dueDate: "2023-05-18",
        status: "In Progress",
      },
      {
        id: 5,
        title: "Create email templates",
        assignedTo: "David Brown",
        priority: "Low",
        dueDate: "2023-05-25",
        status: "To Do",
      },
      {
        id: 6,
        title: "Optimize database queries",
        assignedTo: "Alex Smith",
        priority: "Medium",
        dueDate: "2023-05-22",
        status: "Completed",
      },
    ],
    ru: [
      {
        id: 1,
        title: "Дизайн новой целевой страницы",
        assignedTo: "Мария Иванова",
        priority: "Высокий",
        dueDate: "2023-05-15",
        status: "В процессе",
      },
      {
        id: 2,
        title: "Исправить проблемы с входом",
        assignedTo: "Алексей Смирнов",
        priority: "Высокий",
        dueDate: "2023-05-10",
        status: "К выполнению",
      },
      {
        id: 3,
        title: "Обновить документацию",
        assignedTo: "Иван Петров",
        priority: "Средний",
        dueDate: "2023-05-20",
        status: "На проверке",
      },
      {
        id: 4,
        title: "Внедрить платежный шлюз",
        assignedTo: "Елена Сидорова",
        priority: "Высокий",
        dueDate: "2023-05-18",
        status: "В процессе",
      },
      {
        id: 5,
        title: "Создать шаблоны писем",
        assignedTo: "Дмитрий Козлов",
        priority: "Низкий",
        dueDate: "2023-05-25",
        status: "К выполнению",
      },
      {
        id: 6,
        title: "Оптимизировать запросы к базе данных",
        assignedTo: "Алексей Смирнов",
        priority: "Средний",
        dueDate: "2023-05-22",
        status: "Завершено",
      },
    ],
    uk: [
      {
        id: 1,
        title: "Дизайн нової цільової сторінки",
        assignedTo: "Марія Іванова",
        priority: "Високий",
        dueDate: "2023-05-15",
        status: "В процесі",
      },
      {
        id: 2,
        title: "Виправити проблеми з входом",
        assignedTo: "Олексій Смирнов",
        priority: "Високий",
        dueDate: "2023-05-10",
        status: "До виконання",
      },
      {
        id: 3,
        title: "Оновити документацію",
        assignedTo: "Іван Петров",
        priority: "Середній",
        dueDate: "2023-05-20",
        status: "На перевірці",
      },
      {
        id: 4,
        title: "Впровадити платіжний шлюз",
        assignedTo: "Олена Сидорова",
        priority: "Високий",
        dueDate: "2023-05-18",
        status: "В процесі",
      },
      {
        id: 5,
        title: "Створити шаблони листів",
        assignedTo: "Дмитро Козлов",
        priority: "Низький",
        dueDate: "2023-05-25",
        status: "До виконання",
      },
      {
        id: 6,
        title: "Оптимізувати запити до бази даних",
        assignedTo: "Олексій Смирнов",
        priority: "Середній",
        dueDate: "2023-05-22",
        status: "Завершено",
      },
    ],
    ro: [
      {
        id: 1,
        title: "Design pagină de destinație nouă",
        assignedTo: "Maria Ionescu",
        priority: "Ridicată",
        dueDate: "2023-05-15",
        status: "În desfășurare",
      },
      {
        id: 2,
        title: "Rezolvare probleme de autentificare",
        assignedTo: "Alex Popescu",
        priority: "Ridicată",
        dueDate: "2023-05-10",
        status: "De făcut",
      },
      {
        id: 3,
        title: "Actualizare documentație",
        assignedTo: "Ion Popa",
        priority: "Medie",
        dueDate: "2023-05-20",
        status: "În revizuire",
      },
      {
        id: 4,
        title: "Implementare gateway de plată",
        assignedTo: "Elena Dumitru",
        priority: "Ridicată",
        dueDate: "2023-05-18",
        status: "În desfășurare",
      },
      {
        id: 5,
        title: "Creare șabloane de email",
        assignedTo: "David Stanescu",
        priority: "Scăzută",
        dueDate: "2023-05-25",
        status: "De făcut",
      },
      {
        id: 6,
        title: "Optimizare interogări bază de date",
        assignedTo: "Alex Popescu",
        priority: "Medie",
        dueDate: "2023-05-22",
        status: "Finalizat",
      },
    ],
  }

  const currentTasks = tasks[language]

  const getPriorityColor = (priority: string) => {
    const priorityMap = {
      High: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Medium: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Low: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Высокий: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Средний: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Низкий: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Високий: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Середній: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Низький: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Ridicată: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Medie: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Scăzută: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
    }
    return priorityMap[priority as keyof typeof priorityMap] || "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20"
  }

  const getStatusColor = (status: string) => {
    const statusMap = {
      "To Do": "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20",
      "In Progress": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      Review: "bg-purple-500/10 text-purple-500 hover:bg-purple-500/20",
      Completed: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "К выполнению": "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20",
      "В процессе": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      "На проверке": "bg-purple-500/10 text-purple-500 hover:bg-purple-500/20",
      Завершено: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "До виконання": "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20",
      "В процесі": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      "На перевірці": "bg-purple-500/10 text-purple-500 hover:bg-purple-500/20",
      Завершено: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "De făcut": "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20",
      "În desfășurare": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      "În revizuire": "bg-purple-500/10 text-purple-500 hover:bg-purple-500/20",
      Finalizat: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
    }
    return statusMap[status as keyof typeof statusMap] || "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20"
  }

  const formatDate = (dateString: string) => {
    const date = new Date(dateString)
    return new Intl.DateTimeFormat(
      language === "en" ? "en-US" : language === "ru" ? "ru-RU" : language === "uk" ? "uk-UA" : "ro-RO",
      {
        year: "numeric",
        month: "short",
        day: "numeric",
      },
    ).format(date)
  }

  return (
    <Card>
      <CardContent className="p-0">
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("tasks", "title")}</TableHead>
              <TableHead>{t("tasks", "assignedTo")}</TableHead>
              <TableHead>{t("tasks", "priority")}</TableHead>
              <TableHead>{t("tasks", "dueDate")}</TableHead>
              <TableHead>{t("tasks", "status")}</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentTasks.map((task) => (
              <TableRow key={task.id}>
                <TableCell className="font-medium">{task.title}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <Avatar className="h-6 w-6">
                      <AvatarImage src={`/placeholder.svg?height=24&width=24`} alt={task.assignedTo} />
                      <AvatarFallback>
                        {task.assignedTo
                          .split(" ")
                          .map((n) => n[0])
                          .join("")}
                      </AvatarFallback>
                    </Avatar>
                    <span>{task.assignedTo}</span>
                  </div>
                </TableCell>
                <TableCell>
                  <Badge className={getPriorityColor(task.priority)} variant="outline">
                    {task.priority}
                  </Badge>
                </TableCell>
                <TableCell>{formatDate(task.dueDate)}</TableCell>
                <TableCell>
                  <Badge className={getStatusColor(task.status)} variant="outline">
                    {task.status}
                  </Badge>
                </TableCell>
                <TableCell>
                  <DropdownMenu>
                    <DropdownMenuTrigger asChild>
                      <Button variant="ghost" size="icon">
                        <MoreHorizontal className="h-4 w-4" />
                        <span className="sr-only">Menu</span>
                      </Button>
                    </DropdownMenuTrigger>
                    <DropdownMenuContent align="end">
                      <DropdownMenuItem>{t("projects", "view")}</DropdownMenuItem>
                      <DropdownMenuItem>{t("projects", "edit")}</DropdownMenuItem>
                      <DropdownMenuItem>{t("clients", "delete")}</DropdownMenuItem>
                    </DropdownMenuContent>
                  </DropdownMenu>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
