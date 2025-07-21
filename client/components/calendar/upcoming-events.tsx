"use client"

import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { useLanguage } from "@/client/i18n/language-context"
import { Clock, Calendar, MapPin } from "lucide-react"

interface Event {
  id: number
  title: string
  date: Date
  type: string
  location?: string
  time?: string
}

interface UpcomingEventsProps {
  events: Event[]
}

export function UpcomingEvents({ events }: UpcomingEventsProps) {
  const { t, language } = useLanguage()

  // Sort events by date
  const sortedEvents = [...events].sort((a, b) => a.date.getTime() - b.date.getTime())

  // Format date based on language
  const formatDate = (date: Date) => {
    return new Intl.DateTimeFormat(
      language === "en" ? "en-US" : language === "ru" ? "ru-RU" : language === "uk" ? "uk-UA" : "ro-RO",
      {
        month: "short",
        day: "numeric",
      },
    ).format(date)
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>{t("calendar", "upcoming")}</CardTitle>
        <CardDescription>{t("calendar", "events")}</CardDescription>
      </CardHeader>
      <CardContent>
        {sortedEvents.length > 0 ? (
          <div className="space-y-4">
            {sortedEvents.map((event) => (
              <div key={event.id} className="flex flex-col gap-2 rounded-md border p-3 hover:bg-muted/50">
                <div className="font-medium">{event.title}</div>
                <div className="flex items-center gap-2 text-sm text-muted-foreground">
                  <Calendar className="h-4 w-4" />
                  <span>{formatDate(event.date)}</span>
                </div>
                {event.time && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-4 w-4" />
                    <span>{event.time}</span>
                  </div>
                )}
                {event.location && (
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <MapPin className="h-4 w-4" />
                    <span>{event.location}</span>
                  </div>
                )}
              </div>
            ))}
          </div>
        ) : (
          <div className="text-center py-4 text-muted-foreground">{t("calendar", "noEvents")}</div>
        )}
      </CardContent>
    </Card>
  )
}
