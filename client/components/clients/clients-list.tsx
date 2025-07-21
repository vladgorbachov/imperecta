"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { DropdownMenu, DropdownMenuContent, DropdownMenuItem, DropdownMenuTrigger } from "@/client/components/ui/dropdown-menu"
import { Button } from "@/client/components/ui/button"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { MoreHorizontal, Building2 } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function ClientsList() {
  const { t, language } = useLanguage()

  const clients = {
    en: [
      {
        id: 1,
        name: "Tech Solutions Inc.",
        contact: "John Peterson",
        email: "john@techsolutions.com",
        phone: "+1 (555) 123-4567",
        projects: 3,
      },
      {
        id: 2,
        name: "Ivanov Enterprises",
        contact: "Alex Ivanov",
        email: "alex@ivanov.com",
        phone: "+1 (555) 987-6543",
        projects: 1,
      },
      {
        id: 3,
        name: "Creative LLC",
        contact: "Maria Johnson",
        email: "maria@creative.com",
        phone: "+1 (555) 111-2233",
        projects: 2,
      },
      {
        id: 4,
        name: "Marketing Plus LLC",
        contact: "David Kozlov",
        email: "david@marketingplus.com",
        phone: "+1 (555) 444-5566",
        projects: 1,
      },
      {
        id: 5,
        name: "Business Solutions LLC",
        contact: "Elena Smith",
        email: "elena@businesssolutions.com",
        phone: "+1 (555) 777-8899",
        projects: 2,
      },
    ],
    ru: [
      {
        id: 1,
        name: 'ООО "Технологии"',
        contact: "Иван Петров",
        email: "ivan@tech.ru",
        phone: "+7 (999) 123-45-67",
        projects: 3,
      },
      {
        id: 2,
        name: "ИП Иванов",
        contact: "Алексей Иванов",
        email: "alexey@ivanov.ru",
        phone: "+7 (999) 987-65-43",
        projects: 1,
      },
      {
        id: 3,
        name: 'ЗАО "Креатив"',
        contact: "Мария Сидорова",
        email: "maria@creative.ru",
        phone: "+7 (999) 111-22-33",
        projects: 2,
      },
      {
        id: 4,
        name: 'ООО "Маркетинг Плюс"',
        contact: "Дмитрий Козлов",
        email: "dmitry@marketing.ru",
        phone: "+7 (999) 444-55-66",
        projects: 1,
      },
      {
        id: 5,
        name: 'ООО "Бизнес Решения"',
        contact: "Елена Смирнова",
        email: "elena@business.ru",
        phone: "+7 (999) 777-88-99",
        projects: 2,
      },
    ],
    uk: [
      {
        id: 1,
        name: 'ТОВ "Технології"',
        contact: "Іван Петров",
        email: "ivan@tech.ua",
        phone: "+380 (99) 123-45-67",
        projects: 3,
      },
      {
        id: 2,
        name: "ФОП Іванов",
        contact: "Олексій Іванов",
        email: "oleksiy@ivanov.ua",
        phone: "+380 (99) 987-65-43",
        projects: 1,
      },
      {
        id: 3,
        name: 'ЗАТ "Креатив"',
        contact: "Марія Сидорова",
        email: "maria@creative.ua",
        phone: "+380 (99) 111-22-33",
        projects: 2,
      },
      {
        id: 4,
        name: 'ТОВ "Маркетинг Плюс"',
        contact: "Дмитро Козлов",
        email: "dmytro@marketing.ua",
        phone: "+380 (99) 444-55-66",
        projects: 1,
      },
      {
        id: 5,
        name: 'ТОВ "Бізнес Рішення"',
        contact: "Олена Смирнова",
        email: "olena@business.ua",
        phone: "+380 (99) 777-88-99",
        projects: 2,
      },
    ],
    ro: [
      {
        id: 1,
        name: "Tehnologii SRL",
        contact: "Ion Popescu",
        email: "ion@tech.ro",
        phone: "+40 (799) 123-456",
        projects: 3,
      },
      {
        id: 2,
        name: "Ivanov PFA",
        contact: "Alexandru Ivanov",
        email: "alexandru@ivanov.ro",
        phone: "+40 (799) 987-654",
        projects: 1,
      },
      {
        id: 3,
        name: "Creativ SA",
        contact: "Maria Ionescu",
        email: "maria@creative.ro",
        phone: "+40 (799) 111-223",
        projects: 2,
      },
      {
        id: 4,
        name: "Marketing Plus SRL",
        contact: "David Kozlov",
        email: "david@marketing.ro",
        phone: "+40 (799) 444-556",
        projects: 1,
      },
      {
        id: 5,
        name: "Soluții de Afaceri SRL",
        contact: "Elena Dumitru",
        email: "elena@business.ro",
        phone: "+40 (799) 777-889",
        projects: 2,
      },
    ],
  }

  const currentClients = clients[language]

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("clients", "allClients")}</CardTitle>
        <CardDescription>{t("clients", "manageClients")}</CardDescription>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("clients", "company")}</TableHead>
              <TableHead>{t("clients", "contactPerson")}</TableHead>
              <TableHead>{t("clients", "email")}</TableHead>
              <TableHead>{t("clients", "phone")}</TableHead>
              <TableHead>{t("clients", "projectsCount")}</TableHead>
              <TableHead className="w-[50px]"></TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentClients.map((client) => (
              <TableRow key={client.id}>
                <TableCell>
                  <div className="flex items-center gap-3">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={`/placeholder.svg?height=32&width=32`} alt={client.name} />
                      <AvatarFallback>
                        <Building2 className="h-4 w-4" />
                      </AvatarFallback>
                    </Avatar>
                    <span className="font-medium">{client.name}</span>
                  </div>
                </TableCell>
                <TableCell>{client.contact}</TableCell>
                <TableCell>{client.email}</TableCell>
                <TableCell>{client.phone}</TableCell>
                <TableCell>{client.projects}</TableCell>
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
