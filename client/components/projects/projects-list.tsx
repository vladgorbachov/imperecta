"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { Badge } from "@/client/components/ui/badge"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/client/components/ui/dropdown-menu"
import { Button } from "@/client/components/ui/button"
import { MoreHorizontal } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function ProjectsList() {
  const { t, language } = useLanguage()

  const projects = {
    en: [
      {
        id: 1,
        name: "Website Development",
        client: "Tech Solutions Inc.",
        status: "In Progress",
        deadline: "15.05.2023",
        progress: 65,
      },
      {
        id: 2,
        name: "Mobile Application",
        client: "Ivanov Enterprises",
        status: "Completed",
        deadline: "10.03.2023",
        progress: 100,
      },
      {
        id: 3,
        name: "Logo Redesign",
        client: "Creative LLC",
        status: "Pending",
        deadline: "20.06.2023",
        progress: 0,
      },
      {
        id: 4,
        name: "SEO Optimization",
        client: "Marketing Plus LLC",
        status: "In Progress",
        deadline: "30.05.2023",
        progress: 45,
      },
      {
        id: 5,
        name: "CRM Integration",
        client: "Business Solutions LLC",
        status: "In Progress",
        deadline: "05.06.2023",
        progress: 30,
      },
    ],
    ru: [
      {
        id: 1,
        name: "Разработка веб-сайта",
        client: 'ООО "Технологии"',
        status: "В процессе",
        deadline: "15.05.2023",
        progress: 65,
      },
      {
        id: 2,
        name: "Мобильное приложение",
        client: "ИП Иванов",
        status: "Завершен",
        deadline: "10.03.2023",
        progress: 100,
      },
      {
        id: 3,
        name: "Редизайн логотипа",
        client: 'ЗАО "Креатив"',
        status: "Ожидает",
        deadline: "20.06.2023",
        progress: 0,
      },
      {
        id: 4,
        name: "SEO оптимизация",
        client: 'ООО "Маркетинг Плюс"',
        status: "В процессе",
        deadline: "30.05.2023",
        progress: 45,
      },
      {
        id: 5,
        name: "Интеграция CRM",
        client: 'ООО "Бизнес Решения"',
        status: "В процессе",
        deadline: "05.06.2023",
        progress: 30,
      },
    ],
    uk: [
      {
        id: 1,
        name: "Розробка веб-сайту",
        client: 'ТОВ "Технології"',
        status: "В процесі",
        deadline: "15.05.2023",
        progress: 65,
      },
      {
        id: 2,
        name: "Мобільний додаток",
        client: "ФОП Іванов",
        status: "Завершено",
        deadline: "10.03.2023",
        progress: 100,
      },
      {
        id: 3,
        name: "Редизайн логотипу",
        client: 'ЗАТ "Креатив"',
        status: "Очікує",
        deadline: "20.06.2023",
        progress: 0,
      },
      {
        id: 4,
        name: "SEO оптимізація",
        client: 'ТОВ "Маркетинг Плюс"',
        status: "В процесі",
        deadline: "30.05.2023",
        progress: 45,
      },
      {
        id: 5,
        name: "Інтеграція CRM",
        client: 'ТОВ "Бізнес Рішення"',
        status: "В процесі",
        deadline: "05.06.2023",
        progress: 30,
      },
    ],
    ro: [
      {
        id: 1,
        name: "Dezvoltare site web",
        client: "Tehnologii SRL",
        status: "În desfășurare",
        deadline: "15.05.2023",
        progress: 65,
      },
      {
        id: 2,
        name: "Aplicație mobilă",
        client: "Ivanov PFA",
        status: "Finalizat",
        deadline: "10.03.2023",
        progress: 100,
      },
      {
        id: 3,
        name: "Redesign logo",
        client: "Creativ SA",
        status: "În așteptare",
        deadline: "20.06.2023",
        progress: 0,
      },
      {
        id: 4,
        name: "Optimizare SEO",
        client: "Marketing Plus SRL",
        status: "În desfășurare",
        deadline: "30.05.2023",
        progress: 45,
      },
      {
        id: 5,
        name: "Integrare CRM",
        client: "Soluții de Afaceri SRL",
        status: "În desfășurare",
        deadline: "05.06.2023",
        progress: 30,
      },
    ],
  }

  const currentProjects = projects[language]

  const getStatusColor = (status: string) => {
    const statusMap = {
      "In Progress": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      Completed: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Pending: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      "В процессе": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      Завершен: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Ожидает: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      "В процесі": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      Завершено: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Очікує: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      "În desfășurare": "bg-blue-500/10 text-blue-500 hover:bg-blue-500/20",
      Finalizat: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "În așteptare": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
    }
    return statusMap[status as keyof typeof statusMap] || "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20"
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("projects", "allProjects")}</CardTitle>
        <CardDescription>{t("projects", "manageProjects")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("projects", "name")}</TableHead>
              <TableHead>{t("projects", "client")}</TableHead>
              <TableHead>{t("projects", "status")}</TableHead>
              <TableHead>{t("projects", "deadline")}</TableHead>
              <TableHead>{t("projects", "progress")}</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentProjects.map((project) => (
              <TableRow key={project.id}>
                <TableCell className="font-medium">{project.name}</TableCell>
                <TableCell>{project.client}</TableCell>
                <TableCell>
                  <Badge className={getStatusColor(project.status)} variant="outline">
                    {project.status}
                  </Badge>
                </TableCell>
                <TableCell>{project.deadline}</TableCell>
                <TableCell>
                  <div className="flex items-center gap-2">
                    <div className="h-2 w-full rounded-full bg-muted">
                      <div className="h-full rounded-full bg-primary" style={{ width: `${project.progress}%` }} />
                    </div>
                    <span className="text-xs font-medium">{project.progress}%</span>
                  </div>
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
                      <DropdownMenuItem>{t("projects", "archive")}</DropdownMenuItem>
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
