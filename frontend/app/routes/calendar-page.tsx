import { useState, useEffect } from "react"
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, startOfWeek, endOfWeek, addMonths, subMonths } from "date-fns"
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { Badge } from "@/shared/components/ui/badge"
import { Input } from "@/shared/components/ui/input"
import { 
  ChevronLeft, 
  ChevronRight, 
  Plus, 
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Users,
  Edit,
  Trash2,
  Search,
  Filter
} from "lucide-react"
import { cn } from "@/shared/utils/cn"
import { useLanguage } from "@/app/providers/language-provider"
import { useSupabase } from "@/shared/contexts/supabase-context"
import { EventModal } from "@/shared/components/calendar/event-modal"
import type { CalendarBusEvent } from "@/shared/utils/calendar-bus"

interface Event {
  id: string
  title: string
  description?: string
  date: Date
  time: string
  endTime?: string
  location?: string
  attendees?: string[]
  type: 'meeting' | 'deadline' | 'reminder' | 'event'
  color?: string
}

const mockEvents: Event[] = []

export default function CalendarPage() {
  const { t, language } = useLanguage()
  const { databaseUser } = useSupabase()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date())
  const [events, setEvents] = useState<Event[]>(mockEvents)
  const [isEventModalOpen, setIsEventModalOpen] = useState(false)
  const [editingEvent, setEditingEvent] = useState<Event | undefined>()
  const [viewMode, setViewMode] = useState<'month' | 'week' | 'day'>('month')

  useEffect(() => {
    // Load user events from API
    (async () => {
      try {
        if (!databaseUser?.id) return
        const list = await fetch(`/api/users/${databaseUser.id}/events`).then(r => r.json())
        const mapped: Event[] = (list || []).map((e: any) => ({
          id: e.id,
          title: e.title,
          description: e.description || undefined,
          date: new Date(e.start_at),
          time: new Date(e.start_at).toISOString().substring(11,16),
          endTime: e.end_at ? new Date(e.end_at).toISOString().substring(11,16) : undefined,
          location: e.location || undefined,
          attendees: e.attendees ? JSON.parse(e.attendees) : undefined,
          type: (e.type || 'event'),
          color: e.color || 'bg-blue-500',
        }))
        setEvents(mapped)
      } catch {}
    })()

    const handler = (e: Event | CustomEvent) => {
      const ce = e as CustomEvent<CalendarBusEvent>
      if (!ce.detail) return
      const incoming = ce.detail
      const exists = events.some(ev => ev.id === incoming.id)
      if (exists) return
      setEvents(prev => [
        ...prev,
        {
          id: incoming.id || `${Date.now()}`,
          title: incoming.title,
          description: incoming.description,
          date: incoming.date instanceof Date ? incoming.date : new Date(incoming.date),
          time: incoming.time || '09:00',
          endTime: incoming.endTime,
          location: incoming.location,
          attendees: incoming.attendees,
          type: incoming.type || 'event',
          color: incoming.color || 'bg-blue-500',
        },
      ])
    }
    window.addEventListener('imperecta:calendar:add', handler as EventListener)
    return () => window.removeEventListener('imperecta:calendar:add', handler as EventListener)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [events])

  const monthStart = startOfMonth(currentDate)
  const monthEnd = endOfMonth(currentDate)
  const calendarStart = startOfWeek(monthStart)
  const calendarEnd = endOfWeek(monthEnd)
  const days = eachDayOfInterval({ start: calendarStart, end: calendarEnd })

  const getEventsForDate = (date: Date) => {
    return events.filter(event => isSameDay(event.date, date))
  }

  const handlePrevMonth = () => setCurrentDate(subMonths(currentDate, 1))
  const handleNextMonth = () => setCurrentDate(addMonths(currentDate, 1))
  const handleToday = () => {
    setCurrentDate(new Date())
    setSelectedDate(new Date())
  }

  const handleSaveEvent = async (event: Event) => {
    setEditingEvent(undefined)
    if (!databaseUser?.id) return
    const payload = {
      id: event.id,
      title: event.title,
      description: event.description,
      start_at: new Date(event.date.getFullYear(), event.date.getMonth(), event.date.getDate(), parseInt(event.time.split(':')[0]), parseInt(event.time.split(':')[1])).toISOString(),
      end_at: event.endTime ? new Date(event.date.getFullYear(), event.date.getMonth(), event.date.getDate(), parseInt(event.endTime.split(':')[0]), parseInt(event.endTime.split(':')[1])).toISOString() : null,
      location: event.location,
      type: event.type,
      color: event.color,
      attendees: event.attendees,
    }
    const method = events.some(e => e.id === event.id) ? 'PUT' : 'POST'
    const url = method === 'PUT' ? `/api/users/${databaseUser.id}/events/${event.id}` : `/api/users/${databaseUser.id}/events`
    const res = await fetch(url, { method, headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(payload) })
    if (res.ok) {
      // Reload
      const list = await fetch(`/api/users/${databaseUser.id}/events`).then(r => r.json())
      const mapped: Event[] = (list || []).map((e: any) => ({
        id: e.id,
        title: e.title,
        description: e.description || undefined,
        date: new Date(e.start_at),
        time: new Date(e.start_at).toISOString().substring(11,16),
        endTime: e.end_at ? new Date(e.end_at).toISOString().substring(11,16) : undefined,
        location: e.location || undefined,
        attendees: e.attendees ? JSON.parse(e.attendees) : undefined,
        type: (e.type || 'event'),
        color: e.color || 'bg-blue-500',
      }))
      setEvents(mapped)
    }
  }

  const handleDeleteEvent = async (eventId: string) => {
    if (!databaseUser?.id) return
    await fetch(`/api/users/${databaseUser.id}/events/${eventId}`, { method: 'DELETE' })
    const list = await fetch(`/api/users/${databaseUser.id}/events`).then(r => r.json())
    const mapped: Event[] = (list || []).map((e: any) => ({
      id: e.id,
      title: e.title,
      description: e.description || undefined,
      date: new Date(e.start_at),
      time: new Date(e.start_at).toISOString().substring(11,16),
      endTime: e.end_at ? new Date(e.end_at).toISOString().substring(11,16) : undefined,
      location: e.location || undefined,
      attendees: e.attendees ? JSON.parse(e.attendees) : undefined,
      type: (e.type || 'event'),
      color: e.color || 'bg-blue-500',
    }))
    setEvents(mapped)
  }

  const handleEditEvent = (event: Event) => {
    setEditingEvent(event)
    setIsEventModalOpen(true)
  }

  const weekDays = [t('', 'sun'), t('', 'mon'), t('', 'tue'), t('', 'wed'), t('', 'thu'), t('', 'fri'), t('', 'sat')]

  return (
    <div className="h-[calc(100vh-64px)] flex flex-col bg-background">
      {/* Header */}
      <div className="border-b bg-card/50 backdrop-blur-sm">
        <div className="flex items-center justify-between p-4">
          <div className="flex items-center gap-4">
            <h1 className="text-2xl font-bold dark:gradient-text">
              {format(currentDate, 'MMMM yyyy')}
            </h1>
            <div className="flex items-center gap-1">
              <Button
                variant="ghost"
                size="icon"
                onClick={handlePrevMonth}
                className="h-8 w-8 dark:neon-glow"
              >
                <ChevronLeft className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="icon"
                onClick={handleNextMonth}
                className="h-8 w-8 dark:neon-glow"
              >
                <ChevronRight className="h-4 w-4" />
              </Button>
              <Button
                variant="ghost"
                size="sm"
                onClick={handleToday}
                className="ml-2 dark:neon-glow"
              >
                {t('', 'today')}
              </Button>
            </div>
          </div>
          
          <div className="relative">
            <Search className="absolute left-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
            <Input
              placeholder={t('', 'searchEvents')}
              className="w-64 pl-9 dark:neon-glow"
            />
          </div>
        </div>
      </div>
      
      {/* Calendar Grid */}
      <div className="flex-1 flex">
        <div className="flex-1 p-6">
          <div className="h-full bg-card rounded-lg border dark:neon-glow">
            {/* Week Days Header */}
            <div className="grid grid-cols-7 border-b">
              {weekDays.map(day => (
                <div key={day} className="p-4 text-center text-sm font-medium text-muted-foreground">
                  {day}
                </div>
              ))}
            </div>
            {/* Calendar Days */}
            <div className="grid grid-cols-7 flex-1">
              {days.map((day, idx) => {
                const dayEvents = getEventsForDate(day)
                const isToday = isSameDay(day, new Date())
                const isSelected = selectedDate && isSameDay(day, selectedDate)
                const isCurrentMonth = isSameMonth(day, currentDate)
                return (
                  <div
                    key={idx}
                    onClick={() => setSelectedDate(day)}
                    className={cn(
                      "min-h-[120px] p-2 border-r border-b cursor-pointer transition-colors",
                      !isCurrentMonth && "bg-muted/30",
                      isSelected && "bg-primary/10 dark:bg-accent-blue/10",
                      "hover:bg-muted/50 dark:hover:bg-accent-blue/5"
                    )}
                  >
                    <div className="flex items-center justify-between mb-1">
                      <span className={cn(
                        "text-sm font-medium",
                        !isCurrentMonth && "text-muted-foreground",
                        isToday && "bg-primary text-primary-foreground rounded-full w-7 h-7 flex items-center justify-center dark:bg-accent-blue"
                      )}>
                        {format(day, 'd')}
                      </span>
                      {dayEvents.length > 0 && (
                        <Badge variant="secondary" className="text-xs">
                          {dayEvents.length}
                        </Badge>
                      )}
                    </div>
                    <div className="space-y-1">
                      {dayEvents.slice(0, 3).map(event => (
                        <div
                          key={event.id}
                          onClick={(e) => { e.stopPropagation(); handleEditEvent(event) }}
                          className={cn("text-xs p-1 rounded truncate cursor-pointer transition-opacity hover:opacity-80", event.color || "bg-blue-500", "text-white")}
                        >
                          {event.time} {event.title}
                        </div>
                      ))}
                      {dayEvents.length > 3 && (
                        <div className="text-xs text-muted-foreground">+{dayEvents.length - 3} {t('', 'more')}</div>
                      )}
                    </div>
                  </div>
                )
              })}
            </div>
          </div>
        </div>
        {selectedDate && (
          <div className="w-96 border-l p-6 bg-card/50">
            <div className="mb-6">
              <div className="flex items-center justify-between">
                <div>
                  <h2 className="text-lg font-semibold dark:gradient-text">{format(selectedDate, 'EEEE, MMMM d')}</h2>
                  <p className="text-sm text-muted-foreground">{getEventsForDate(selectedDate).length} {t('', 'events')}</p>
                </div>
                <Button size="sm" onClick={() => setIsEventModalOpen(true)} className="dark:neon-glow">
                  {t('', 'addEvent')}
                </Button>
              </div>
            </div>
            <div className="space-y-3">
              {getEventsForDate(selectedDate).length > 0 ? (
                getEventsForDate(selectedDate).map(event => (
                  <Card key={event.id} className="dark:neon-glow"><CardContent className="p-4">
                    <div className="flex items-start justify-between">
                      <div className="flex-1">
                        <div className="flex items-center gap-2 mb-1">
                          <div className={cn("w-3 h-3 rounded-full", event.color || "bg-blue-500")} />
                          <h3 className="font-medium">{event.title}</h3>
                        </div>
                        <div className="space-y-1 text-sm text-muted-foreground">
                          <div className="flex items-center gap-2"><Clock className="h-3 w-3" /><span>{event.time}{event.endTime && ` - ${event.endTime}`}</span></div>
                          {event.location && (<div className="flex items-center gap-2"><MapPin className="h-3 w-3" /><span>{event.location}</span></div>)}
                          {event.attendees && event.attendees.length > 0 && (<div className="flex items-center gap-2"><Users className="h-3 w-3" /><span>{event.attendees.join(", ")}</span></div>)}
                        </div>
                        {event.description && (<p className="text-sm mt-2">{event.description}</p>)}
                      </div>
                      <div className="flex gap-1">
                        <Button variant="ghost" size="icon" className="h-8 w-8 dark:neon-glow" onClick={() => handleEditEvent(event)}><Edit className="h-4 w-4" /></Button>
                        <Button variant="ghost" size="icon" className="h-8 w-8 dark:neon-glow" onClick={() => handleDeleteEvent(event.id)}><Trash2 className="h-4 w-4" /></Button>
                      </div>
                    </div>
                  </CardContent></Card>
                ))
              ) : (
                <div className="py-8">
                  <CalendarIcon className="h-12 w-12 mb-3 text-muted-foreground opacity-50" />
                  <p className="text-muted-foreground mb-3">{t('', 'noEvents')}</p>
                </div>
              )}
            </div>
          </div>
        )}
      </div>
      <EventModal event={editingEvent} isOpen={isEventModalOpen} onOpenChange={setIsEventModalOpen} onSave={handleSaveEvent} onDelete={handleDeleteEvent} selectedDate={selectedDate} />
    </div>
  )
}
