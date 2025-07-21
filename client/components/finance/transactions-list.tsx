"use client"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/client/components/ui/table"
import { Button } from "@/client/components/ui/button"
import { Plus } from "lucide-react"
import { useLanguage } from "@/client/i18n/language-context"

export function TransactionsList() {
  const { t, language } = useLanguage()

  const transactions = {
    en: [
      {
        id: 1,
        date: "2023-05-01",
        category: "Sales",
        amount: 12500,
        description: "Website development project",
      },
      {
        id: 2,
        date: "2023-05-03",
        category: "Rent",
        amount: -2000,
        description: "Office rent for May",
      },
      {
        id: 3,
        date: "2023-05-05",
        category: "Utilities",
        amount: -350,
        description: "Electricity bill",
      },
      {
        id: 4,
        date: "2023-05-10",
        category: "Sales",
        amount: 8500,
        description: "Mobile app development",
      },
      {
        id: 5,
        date: "2023-05-15",
        category: "Salaries",
        amount: -15000,
        description: "Employee salaries",
      },
    ],
    ru: [
      {
        id: 1,
        date: "2023-05-01",
        category: "Продажи",
        amount: 12500,
        description: "Проект разработки веб-сайта",
      },
      {
        id: 2,
        date: "2023-05-03",
        category: "Аренда",
        amount: -2000,
        description: "Аренда офиса за май",
      },
      {
        id: 3,
        date: "2023-05-05",
        category: "Коммунальные услуги",
        amount: -350,
        description: "Счет за электричество",
      },
      {
        id: 4,
        date: "2023-05-10",
        category: "Продажи",
        amount: 8500,
        description: "Разработка мобильного приложения",
      },
      {
        id: 5,
        date: "2023-05-15",
        category: "Зарплаты",
        amount: -15000,
        description: "Зарплаты сотрудников",
      },
    ],
    uk: [
      {
        id: 1,
        date: "2023-05-01",
        category: "Продажі",
        amount: 12500,
        description: "Проект розробки веб-сайту",
      },
      {
        id: 2,
        date: "2023-05-03",
        category: "Оренда",
        amount: -2000,
        description: "Оренда офісу за травень",
      },
      {
        id: 3,
        date: "2023-05-05",
        category: "Комунальні послуги",
        amount: -350,
        description: "Рахунок за електроенергію",
      },
      {
        id: 4,
        date: "2023-05-10",
        category: "Продажі",
        amount: 8500,
        description: "Розробка мобільного додатку",
      },
      {
        id: 5,
        date: "2023-05-15",
        category: "Зарплати",
        amount: -15000,
        description: "Зарплати співробітників",
      },
    ],
    ro: [
      {
        id: 1,
        date: "2023-05-01",
        category: "Vânzări",
        amount: 12500,
        description: "Proiect dezvoltare site web",
      },
      {
        id: 2,
        date: "2023-05-03",
        category: "Chirie",
        amount: -2000,
        description: "Chirie birou pentru mai",
      },
      {
        id: 3,
        date: "2023-05-05",
        category: "Utilități",
        amount: -350,
        description: "Factură electricitate",
      },
      {
        id: 4,
        date: "2023-05-10",
        category: "Vânzări",
        amount: 8500,
        description: "Dezvoltare aplicație mobilă",
      },
      {
        id: 5,
        date: "2023-05-15",
        category: "Salarii",
        amount: -15000,
        description: "Salarii angajați",
      },
    ],
  }

  const currentTransactions = transactions[language]

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

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between">
        <div>
          <CardTitle>{t("finance", "transactions")}</CardTitle>
          <CardDescription>{t("finance", "manageFinances")}</CardDescription>
        </div>
        <Button size="sm">
          <Plus className="mr-2 h-4 w-4" />
          {t("finance", "addTransaction")}
        </Button>
      </CardHeader>
      <CardContent>
        <Table>
          <TableHeader>
            <TableRow>
              <TableHead>{t("finance", "date")}</TableHead>
              <TableHead>{t("finance", "category")}</TableHead>
              <TableHead>{t("finance", "amount")}</TableHead>
              <TableHead>{t("finance", "description")}</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody>
            {currentTransactions.map((transaction) => (
              <TableRow key={transaction.id}>
                <TableCell>{formatDate(transaction.date)}</TableCell>
                <TableCell>{transaction.category}</TableCell>
                <TableCell className={transaction.amount > 0 ? "text-green-600" : "text-red-600"}>
                  {formatAmount(transaction.amount)}
                </TableCell>
                <TableCell>{transaction.description}</TableCell>
              </TableRow>
            ))}
          </TableBody>
        </Table>
      </CardContent>
    </Card>
  )
}
