"use client"

import { Button } from "@/client/components/ui/button"
import { Tabs, TabsList, TabsTrigger } from "@/client/components/ui/tabs"
import { Plus, ChevronLeft, ChevronRight } from "lucide-react"
import { useState } from "react"
import { useLanguage } from "@/client/i18n/language-context"

export function CalendarHeader() {
  const { t } = useLanguage()
  const [view, setView] = useState("month")
  const [currentDate, setCurrentDate] = useState(new Date())

  const monthNames = {
    en: [
      "January",
      "February",
      "March",
      "April",
      "May",
      "June",
      "July",
      "August",
      "September",
      "October",
      "November",
      "December",
    ],
    ru: [
      "Январь",
      "Февраль",
      "Март",
      "Апрель",
      "Май",
      "Июнь",
      "Июль",
      "Август",
      "Сентябрь",
      "Октябрь",
      "Ноябрь",
      "Декабрь",
    ],
    uk: [
      "Січень",
      "Лютий",
      "Березень",
      "Квітень",
      "Травень",
      "Червень",
      "Липень",
      "Серпень",
      "Вересень",
      "Жовтень",
      "Листопад",
      "Грудень",
    ],
    ro: [
      "Ianuarie",
      "Februarie",
      "Martie",
      "Aprilie",
      "Mai",
      "Iunie",
      "Iulie",
      "August",
      "Septembrie",
      "Octombrie",
      "Noiembrie",
      "Decembrie",
    ],
  }

  const { language } = useLanguage()
  const month = monthNames[language][currentDate.getMonth()]
  const year = currentDate.getFullYear()

  const goToPreviousMonth = () => {
    const newDate = new Date(currentDate)
    newDate.setMonth(newDate.getMonth() - 1)
    setCurrentDate(newDate)
  }

  const goToNextMonth = () => {
    const newDate = new Date(currentDate)
    newDate.setMonth(newDate.getMonth() + 1)
    setCurrentDate(newDate)
  }

  const goToToday = () => {
    setCurrentDate(new Date())
  }

  return (
    <div className="flex flex-col gap-4 sm:flex-row sm:items-center sm:justify-between">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{t("calendar", "title")}</h1>
        <p className="text-muted-foreground">{t("calendar", "description")}</p>
      </div>
      <div className="flex items-center gap-2">
        <div className="flex items-center gap-2 mr-4">
          <Button variant="outline" size="icon" onClick={goToPreviousMonth}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <div className="min-w-[150px] text-center">
            <span className="font-medium">
              {month} {year}
            </span>
          </div>
          <Button variant="outline" size="icon" onClick={goToNextMonth}>
            <ChevronRight className="h-4 w-4" />
          </Button>
          <Button variant="outline" className="ml-2" onClick={goToToday}>
            {t("calendar", "today")}
          </Button>
        </div>
        <Tabs defaultValue={view} className="w-[300px]" onValueChange={setView}>
          <TabsList>
            <TabsTrigger value="month">{t("calendar", "month")}</TabsTrigger>
            <TabsTrigger value="week">{t("calendar", "week")}</TabsTrigger>
            <TabsTrigger value="day">{t("calendar", "day")}</TabsTrigger>
          </TabsList>
        </Tabs>
        <Button className="ml-2">
          <Plus className="mr-2 h-4 w-4" />
          {t("calendar", "addEvent")}
        </Button>
      </div>
    </div>
  )
}
