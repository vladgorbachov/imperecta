"use client"

import { Card, CardContent } from "@/client/components/ui/card"
import { useLanguage } from "@/client/i18n/language-context"
import { useState, useEffect } from "react"
import { UpcomingEvents } from "./upcoming-events"

export function CalendarView() {
  const { language } = useLanguage()
  const [currentDate] = useState(new Date())
  const [calendarDays, setCalendarDays] = useState<Date[]>([])

  // Day names for different languages
  const dayNames = {
    en: ["Sun", "Mon", "Tue", "Wed", "Thu", "Fri", "Sat"],
    ru: ["Вс", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
    uk: ["Нд", "Пн", "Вт", "Ср", "Чт", "Пт", "Сб"],
    ro: ["Dum", "Lun", "Mar", "Mie", "Joi", "Vin", "Sâm"],
  }

  // Generate calendar days for the current month
  useEffect(() => {
    const year = currentDate.getFullYear()
    const month = currentDate.getMonth()

    // First day of the month
    const firstDay = new Date(year, month, 1)
    // Last day of the month
    const lastDay = new Date(year, month + 1, 0)

    // Get the day of the week for the first day (0 = Sunday, 1 = Monday, etc.)
    const firstDayOfWeek = firstDay.getDay()

    // Calculate days from previous month to show
    const daysFromPrevMonth = firstDayOfWeek
    const prevMonthLastDay = new Date(year, month, 0).getDate()

    const days: Date[] = []

    // Add days from previous month
    for (let i = daysFromPrevMonth - 1; i >= 0; i--) {
      days.push(new Date(year, month - 1, prevMonthLastDay - i))
    }

    // Add days from current month
    for (let i = 1; i <= lastDay.getDate(); i++) {
      days.push(new Date(year, month, i))
    }

    // Add days from next month to complete the grid (6 rows x 7 columns = 42 cells)
    const remainingDays = 42 - days.length
    for (let i = 1; i <= remainingDays; i++) {
      days.push(new Date(year, month + 1, i))
    }

    setCalendarDays(days)
  }, [currentDate])

  // Check if a date is today
  const isToday = (date: Date) => {
    const today = new Date()
    return (
      date.getDate() === today.getDate() &&
      date.getMonth() === today.getMonth() &&
      date.getFullYear() === today.getFullYear()
    )
  }

  // Check if a date is in the current month
  const isCurrentMonth = (date: Date) => {
    return date.getMonth() === currentDate.getMonth()
  }

  // Sample events data
  const events = [
    {
      id: 1,
      title: "Team Meeting",
      date: new Date(currentDate.getFullYear(), currentDate.getMonth(), 15),
      type: "meeting",
    },
    {
      id: 2,
      title: "Project Deadline",
      date: new Date(currentDate.getFullYear(), currentDate.getMonth(), 25),
      type: "deadline",
    },
    {
      id: 3,
      title: "Client Call",
      date: new Date(currentDate.getFullYear(), currentDate.getMonth(), 10),
      type: "meeting",
    },
    {
      id: 4,
      title: "Marketing Campaign",
      date: new Date(currentDate.getFullYear(), currentDate.getMonth(), 5),
      type: "reminder",
    },
  ]

  // Get events for a specific date
  const getEventsForDate = (date: Date) => {
    return events.filter(
      (event) =>
        event.date.getDate() === date.getDate() &&
        event.date.getMonth() === date.getMonth() &&
        event.date.getFullYear() === date.getFullYear(),
    )
  }

  // Get event indicator color based on type
  const getEventColor = (type: string) => {
    switch (type) {
      case "meeting":
        return "bg-blue-500"
      case "deadline":
        return "bg-red-500"
      case "reminder":
        return "bg-yellow-500"
      default:
        return "bg-gray-500"
    }
  }

  return (
    <div className="grid grid-cols-1 gap-6 lg:grid-cols-4">
      <Card className="lg:col-span-3">
        <CardContent className="p-0">
          <div className="grid grid-cols-7 border-b">
            {dayNames[language].map((day, index) => (
              <div key={index} className="p-2 text-center text-sm font-medium border-r last:border-r-0">
                {day}
              </div>
            ))}
          </div>
          <div className="grid grid-cols-7 grid-rows-6 h-[calc(100vh-300px)]">
            {calendarDays.map((date, index) => {
              const dateEvents = getEventsForDate(date)
              return (
                <div
                  key={index}
                  className={`border-r border-b last:border-r-0 p-1 ${
                    isCurrentMonth(date) ? "bg-background" : "bg-muted/30"
                  } ${isToday(date) ? "bg-primary/10" : ""}`}
                >
                  <div className="flex flex-col h-full">
                    <div
                      className={`text-right p-1 ${
                        isToday(date)
                          ? "bg-primary text-primary-foreground rounded-full w-7 h-7 flex items-center justify-center ml-auto"
                          : ""
                      }`}
                    >
                      {date.getDate()}
                    </div>
                    <div className="flex-1 overflow-y-auto">
                      {dateEvents.map((event) => (
                        <div key={event.id} className="text-xs p-1 mb-1 rounded truncate cursor-pointer hover:bg-muted">
                          <div className="flex items-center gap-1">
                            <div className={`w-2 h-2 rounded-full ${getEventColor(event.type)}`}></div>
                            {event.title}
                          </div>
                        </div>
                      ))}
                    </div>
                  </div>
                </div>
              )
            })}
          </div>
        </CardContent>
      </Card>
      <UpcomingEvents events={events} />
    </div>
  )
}
