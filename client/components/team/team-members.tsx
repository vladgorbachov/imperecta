"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/client/components/ui/dropdown-menu"
import { Button } from "@/client/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { Badge } from "@/client/components/ui/badge"
import { MoreHorizontal } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function TeamMembers() {
  const { t, language } = useLanguage()

  const members = {
    en: [
      {
        id: 1,
        name: "John Peterson",
        position: "Project Manager",
        email: "john@company.com",
        department: "Management",
        status: "Active",
      },
      {
        id: 2,
        name: "Maria Johnson",
        position: "Designer",
        email: "maria@company.com",
        department: "Design",
        status: "Active",
      },
      {
        id: 3,
        name: "Alex Smith",
        position: "Developer",
        email: "alex@company.com",
        department: "Development",
        status: "Active",
      },
      {
        id: 4,
        name: "Elena Wilson",
        position: "Marketing Specialist",
        email: "elena@company.com",
        department: "Marketing",
        status: "On Vacation",
      },
      {
        id: 5,
        name: "David Brown",
        position: "Accountant",
        email: "david@company.com",
        department: "Finance",
        status: "Active",
      },
    ],
    ru: [
      {
        id: 1,
        name: "Иван Петров",
        position: "Руководитель проектов",
        email: "ivan@company.ru",
        department: "Управление",
        status: "Активен",
      },
      {
        id: 2,
        name: "Мария Сидорова",
        position: "Дизайнер",
        email: "maria@company.ru",
        department: "Дизайн",
        status: "Активен",
      },
      {
        id: 3,
        name: "Алексей Иванов",
        position: "Разработчик",
        email: "alexey@company.ru",
        department: "Разработка",
        status: "Активен",
      },
      {
        id: 4,
        name: "Елена Смирнова",
        position: "Маркетолог",
        email: "elena@company.ru",
        department: "Маркетинг",
        status: "В отпуске",
      },
      {
        id: 5,
        name: "Дмитрий Козлов",
        position: "Бухгалтер",
        email: "dmitry@company.ru",
        department: "Финансы",
        status: "Активен",
      },
    ],
    uk: [
      {
        id: 1,
        name: "Іван Петров",
        position: "Керівник проектів",
        email: "ivan@company.ua",
        department: "Управління",
        status: "Активний",
      },
      {
        id: 2,
        name: "Марія Сидорова",
        position: "Дизайнер",
        email: "maria@company.ua",
        department: "Дизайн",
        status: "Активний",
      },
      {
        id: 3,
        name: "Олексій Іванов",
        position: "Розробник",
        email: "oleksiy@company.ua",
        department: "Розробка",
        status: "Активний",
      },
      {
        id: 4,
        name: "Олена Смирнова",
        position: "Маркетолог",
        email: "olena@company.ua",
        department: "Маркетинг",
        status: "У відпустці",
      },
      {
        id: 5,
        name: "Дмитро Козлов",
        position: "Бухгалтер",
        email: "dmytro@company.ua",
        department: "Фінанси",
        status: "Активний",
      },
    ],
    ro: [
      {
        id: 1,
        name: "Ion Popescu",
        position: "Manager de proiect",
        email: "ion@company.ro",
        department: "Management",
        status: "Activ",
      },
      {
        id: 2,
        name: "Maria Ionescu",
        position: "Designer",
        email: "maria@company.ro",
        department: "Design",
        status: "Activ",
      },
      {
        id: 3,
        name: "Alexandru Popa",
        position: "Dezvoltator",
        email: "alexandru@company.ro",
        department: "Dezvoltare",
        status: "Activ",
      },
      {
        id: 4,
        name: "Elena Dumitru",
        position: "Specialist marketing",
        email: "elena@company.ro",
        department: "Marketing",
        status: "În concediu",
      },
      {
        id: 5,
        name: "David Stanescu",
        position: "Contabil",
        email: "david@company.ro",
        department: "Finanțe",
        status: "Activ",
      },
    ],
  }

  const currentMembers = members[language]

  const getStatusColor = (status: string) => {
    const statusMap = {
      Active: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "On Vacation": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Активен: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "В отпуске": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Активний: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "У відпустці": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Activ: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "În concediu": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
    }
    return statusMap[status as keyof typeof statusMap] || "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20"
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("team", "employees")}</CardTitle>
        <CardDescription>{t("team", "manageTeam")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("team", "name")}</TableHead>
              <TableHead>{t("team", "position")}</TableHead>
              <TableHead>{t("clients", "email")}</TableHead>
              <TableHead>{t("team", "department")}</TableHead>
              <TableHead>{t("team", "status")}</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentMembers.map((member) => (
              <TableRow key={member.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={`/placeholder.svg?height=32&width=32`} alt={member.name} />
                      <AvatarFallback>
                        {member.name
                          .split(" ")
                          .map((n) => n[0])
                          .join("")}
                      </AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{member.name}</span>
                  </div>
                </TableCell>
                <TableCell>{member.position}</TableCell>
                <TableCell>{member.email}</TableCell>
                <TableCell>{member.department}</TableCell>
                <TableCell>
                  <Badge className={getStatusColor(member.status)} variant="outline">
                    {member.status}
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
                      <DropdownMenuItem>{t("team", "deactivate")}</DropdownMenuItem>
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
