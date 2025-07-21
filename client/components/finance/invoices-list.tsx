"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { Badge } from "@/client/components/ui/badge"
import { Button } from "@/client/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function InvoicesList() {
  const { t, language } = useLanguage()

  const invoices = {
    en: [
      {
        id: 1,
        invoiceNumber: "INV-2023-001",
        client: "Tech Solutions Inc.",
        amount: 12500,
        date: "2023-05-01",
        dueDate: "2023-05-15",
        status: "Paid",
      },
      {
        id: 2,
        invoiceNumber: "INV-2023-002",
        client: "Creative Design Co.",
        amount: 8500,
        date: "2023-05-05",
        dueDate: "2023-05-20",
        status: "Unpaid",
      },
      {
        id: 3,
        invoiceNumber: "INV-2023-003",
        client: "Marketing Plus",
        amount: 5000,
        date: "2023-05-10",
        dueDate: "2023-05-25",
        status: "Unpaid",
      },
      {
        id: 4,
        invoiceNumber: "INV-2023-004",
        client: "Global Enterprises",
        amount: 15000,
        date: "2023-04-15",
        dueDate: "2023-04-30",
        status: "Overdue",
      },
      {
        id: 5,
        invoiceNumber: "INV-2023-005",
        client: "Startup Innovations",
        amount: 7500,
        date: "2023-04-20",
        dueDate: "2023-05-05",
        status: "Paid",
      },
    ],
    ru: [
      {
        id: 1,
        invoiceNumber: "ИНВ-2023-001",
        client: 'ООО "Технологии"',
        amount: 12500,
        date: "2023-05-01",
        dueDate: "2023-05-15",
        status: "Оплачен",
      },
      {
        id: 2,
        invoiceNumber: "ИНВ-2023-002",
        client: 'ЗАО "Креатив"',
        amount: 8500,
        date: "2023-05-05",
        dueDate: "2023-05-20",
        status: "Не оплачен",
      },
      {
        id: 3,
        invoiceNumber: "ИНВ-2023-003",
        client: 'ООО "Маркетинг Плюс"',
        amount: 5000,
        date: "2023-05-10",
        dueDate: "2023-05-25",
        status: "Не оплачен",
      },
      {
        id: 4,
        invoiceNumber: "ИНВ-2023-004",
        client: 'ООО "Глобал"',
        amount: 15000,
        date: "2023-04-15",
        dueDate: "2023-04-30",
        status: "Просрочен",
      },
      {
        id: 5,
        invoiceNumber: "ИНВ-2023-005",
        client: 'ООО "Стартап"',
        amount: 7500,
        date: "2023-04-20",
        dueDate: "2023-05-05",
        status: "Оплачен",
      },
    ],
    uk: [
      {
        id: 1,
        invoiceNumber: "ІНВ-2023-001",
        client: 'ТОВ "Технології"',
        amount: 12500,
        date: "2023-05-01",
        dueDate: "2023-05-15",
        status: "Оплачено",
      },
      {
        id: 2,
        invoiceNumber: "ІНВ-2023-002",
        client: 'ЗАТ "Креатив"',
        amount: 8500,
        date: "2023-05-05",
        dueDate: "2023-05-20",
        status: "Не оплачено",
      },
      {
        id: 3,
        invoiceNumber: "ІНВ-2023-003",
        client: 'ТОВ "Маркетинг Плюс"',
        amount: 5000,
        date: "2023-05-10",
        dueDate: "2023-05-25",
        status: "Не оплачено",
      },
      {
        id: 4,
        invoiceNumber: "ІНВ-2023-004",
        client: 'ТОВ "Глобал"',
        amount: 15000,
        date: "2023-04-15",
        dueDate: "2023-04-30",
        status: "Прострочено",
      },
      {
        id: 5,
        invoiceNumber: "ІНВ-2023-005",
        client: 'ТОВ "Стартап"',
        amount: 7500,
        date: "2023-04-20",
        dueDate: "2023-05-05",
        status: "Оплачено",
      },
    ],
    ro: [
      {
        id: 1,
        invoiceNumber: "FAC-2023-001",
        client: "Tech Solutions SRL",
        amount: 12500,
        date: "2023-05-01",
        dueDate: "2023-05-15",
        status: "Plătit",
      },
      {
        id: 2,
        invoiceNumber: "FAC-2023-002",
        client: "Creative Design SRL",
        amount: 8500,
        date: "2023-05-05",
        dueDate: "2023-05-20",
        status: "Neplătit",
      },
      {
        id: 3,
        invoiceNumber: "FAC-2023-003",
        client: "Marketing Plus SRL",
        amount: 5000,
        date: "2023-05-10",
        dueDate: "2023-05-25",
        status: "Neplătit",
      },
      {
        id: 4,
        invoiceNumber: "FAC-2023-004",
        client: "Global Enterprises SRL",
        amount: 15000,
        date: "2023-04-15",
        dueDate: "2023-04-30",
        status: "Restant",
      },
      {
        id: 5,
        invoiceNumber: "FAC-2023-005",
        client: "Startup Innovations SRL",
        amount: 7500,
        date: "2023-04-20",
        dueDate: "2023-05-05",
        status: "Plătit",
      },
    ],
  }

  const currentInvoices = invoices[language]

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

  const formatAmount = (amount: number) => {
    return new Intl.NumberFormat(
      language === "en" ? "en-US" : language === "ru" ? "ru-RU" : language === "uk" ? "uk-UA" : "ro-RO",
      {
        style: "currency",
        currency: "USD",
      },
    ).format(amount)
  }

  const getStatusColor = (status: string) => {
    const statusMap = {
      Paid: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Unpaid: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Overdue: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Оплачен: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "Не оплачен": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Просрочен: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Оплачено: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      "Не оплачено": "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Прострочено: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
      Plătit: "bg-green-500/10 text-green-500 hover:bg-green-500/20",
      Neplătit: "bg-yellow-500/10 text-yellow-500 hover:bg-yellow-500/20",
      Restant: "bg-red-500/10 text-red-500 hover:bg-red-500/20",
    }
    return statusMap[status as keyof typeof statusMap] || "bg-gray-500/10 text-gray-500 hover:bg-gray-500/20"
  }

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{t("finance", "invoices")}</CardTitle>
          <CardDescription>{t("finance", "manageFinances")}</CardDescription>
        </div>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          {t("finance", "createInvoice")}
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("finance", "invoiceNumber")}</TableHead>
              <TableHead>{t("finance", "client")}</TableHead>
              <TableHead>{t("finance", "amount")}</TableHead>
              <TableHead>{t("finance", "dueDate")}</TableHead>
              <TableHead>{t("finance", "status")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentInvoices.map((invoice) => (
              <TableRow key={invoice.id}>
                <TableCell className="font-medium">{invoice.invoiceNumber}</TableCell>
                <TableCell>{invoice.client}</TableCell>
                <TableCell>{formatAmount(invoice.amount)}</TableCell>
                <TableCell>{formatDate(invoice.dueDate)}</TableCell>
                <TableCell>
                  <Badge className={getStatusColor(invoice.status)} variant="outline">
                    {invoice.status}
                  </Badge>
                </TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
