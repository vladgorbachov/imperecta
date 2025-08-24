import { useState, useEffect, useRef, useMemo } from "react"
import { format, startOfMonth, endOfMonth, eachDayOfInterval, isSameMonth, isSameDay, startOfWeek, endOfWeek, addMonths, subMonths, getWeek } from "date-fns"
import { Card, CardContent } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { Badge } from "@/shared/components/ui/badge"
import { Input } from "@/shared/components/ui/input"
import { 
  ChevronLeft, 
  ChevronRight, 
  Calendar as CalendarIcon,
  Clock,
  MapPin,
  Users,
  Edit,
  Trash2,
  Search
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
  const { t } = useLanguage()
  const { databaseUser } = useSupabase()
  const [currentDate, setCurrentDate] = useState(new Date())
  const [selectedDate, setSelectedDate] = useState<Date | null>(new Date())
  const [events, setEvents] = useState<Event[]>(mockEvents)
  const [isEventModalOpen, setIsEventModalOpen] = useState(false)
  const [editingEvent, setEditingEvent] = useState<Event | undefined>()
  // Using month view only for now

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
      setEvents(prev => {
        const exists = prev.some(ev => ev.id === (incoming.id || ""))
        if (exists) return prev
        return [
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
        ]
      })
    }
    window.addEventListener('imperecta:calendar:add', handler as EventListener)
    return () => window.removeEventListener('imperecta:calendar:add', handler as EventListener)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [databaseUser?.id])

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

  // Grid sizing in a Google Calendar-like layout with shared borders
  const gridAreaRef = useRef<HTMLDivElement | null>(null)
  const WEEK_COL_WIDTH = 44 // px
  const HEADER_ROW_HEIGHT = 44 // px
  const [dayCellWidth, setDayCellWidth] = useState<number>(0)
  const [dayCellHeight, setDayCellHeight] = useState<number>(0)

  const gridDimensions = useMemo(() => {
    const width = WEEK_COL_WIDTH + dayCellWidth * 7
    const height = HEADER_ROW_HEIGHT + dayCellHeight * 6
    return { width, height }
  }, [dayCellWidth, dayCellHeight])

  useEffect(() => {
    const computeSizes = () => {
      const el = gridAreaRef.current
      if (!el) return
      const availableWidth = el.clientWidth
      const availableHeight = Math.max(0, el.clientHeight - 2) // 3px bottom offset
      const computedDayWidth = Math.floor((availableWidth - WEEK_COL_WIDTH) / 7)
      const computedDayHeight = Math.floor((availableHeight - HEADER_ROW_HEIGHT) / 2.2)
      setDayCellWidth(computedDayWidth > 0 ? computedDayWidth : 0)
      setDayCellHeight(computedDayHeight > 0 ? computedDayHeight : 0)
    }
    computeSizes()
    window.addEventListener('resize', computeSizes)
    return () => window.removeEventListener('resize', computeSizes)
  }, [])

  return (
    <div className="calendar-page flex h-full min-h-0 flex-col bg-transparent">
      {/* Header */}
      <div className="bg-transparent">
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
              type="search"
              className="search-input w-48 h-10 pl-9 dark:neon-glow"
            />
          </div>
        </div>
      </div>
      
      {/* Calendar Grid (Google Calendar-like) */}
      <div className="flex-1 flex min-h-0">
        <div className="flex-1 px-3 pt-3 pb-1 min-h-0">
          <div ref={gridAreaRef} className="h-full min-h-0 w-full">
            {/* Outer calendar frame with its own borders and exact fit to the area */}
            <div
              className="calendar-frame border rounded-none overflow-hidden bg-transparent"
              style={{ width: gridDimensions.width > 0 ? `${gridDimensions.width}px` : undefined, height: gridDimensions.height > 0 ? `${gridDimensions.height}px` : undefined }}
            >
              {/* Unified 8x7 grid: 1 header row + 6 week rows; first column is week numbers */}
              <div
                className="grid"
                style={{ gridTemplateColumns: `${WEEK_COL_WIDTH}px repeat(7, ${dayCellWidth}px)`, gridTemplateRows: `${HEADER_ROW_HEIGHT}px repeat(6, ${dayCellHeight}px)` }}
              >
                {/* Header row */}
                <div className={cn("flex items-center justify-center text-xs font-medium text-muted-foreground border-b-2 border-r-2")}>{t('', 'week')}</div>
                {weekDays.map((day, i) => (
                  <div
                    key={`hdr-${i}`}
                    className={cn("flex items-center justify-center text-sm font-medium text-muted-foreground border-b-2", i < 6 && "border-r-2")}
                  >
                    {day}
                  </div>
                ))}

                {/* 6 weeks */}
                {[0, 1, 2, 3, 4, 5].map(weekIdx => {
                  const weekStart = days[weekIdx * 7]
                  const weekNumber = getWeek(weekStart, { weekStartsOn: 0 })
                  const isLastRow = weekIdx === 5
                  return (
                    <>
                      {/* Week number cell */}
                      <div key={`wk-${weekIdx}`} className={cn("flex items-center justify-center text-muted-foreground text-sm font-medium border-r-2", !isLastRow && "border-b-2")}>{weekNumber}</div>
                      {/* Day cells */}
                      {days.slice(weekIdx * 7, (weekIdx + 1) * 7).map((day, dayIdx) => {
                        const idx = weekIdx * 7 + dayIdx
                        const dayEvents = getEventsForDate(day)
                        const isToday = isSameDay(day, new Date())
                        const isSelected = selectedDate && isSameDay(day, selectedDate)
                        const isCurrentMonth = isSameMonth(day, currentDate)
                        const isLastColumn = dayIdx === 6
                        return (
                          <div
                            key={`d-${idx}`}
                            onClick={() => setSelectedDate(day)}
                            className={cn(
                              "h-full min-h-0 p-2 cursor-pointer transition-colors bg-transparent",
                              !isLastColumn && "border-r-2",
                              !isLastRow && "border-b-2",
                              isSelected && "ring-1 ring-[hsl(var(--border))] dark:ring-[hsl(var(--accent-blue))]"
                            )}
                          >
                            <div className="flex items-center justify-between mb-1">
                              <span className={cn(
                                "text-lg font-medium",
                                !isCurrentMonth && "text-muted-foreground",
                                isToday && "bg-primary text-primary-foreground rounded-full w-8 h-8 flex items-center justify-center dark:bg-accent-blue"
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
                              {dayEvents.slice(0, 2).map(event => (
                                <div
                                  key={event.id}
                                  onClick={(e) => { e.stopPropagation(); handleEditEvent(event) }}
                                  className={cn("text-xs p-1 rounded truncate cursor-pointer transition-opacity hover:opacity-80", event.color || "bg-blue-500", "text-white")}
                                >
                                  {event.time} {event.title}
                                </div>
                              ))}
                              {dayEvents.length > 2 && (
                                <div className="text-xs text-muted-foreground">+{dayEvents.length - 2} {t('', 'more')}</div>
                              )}
                            </div>
                          </div>
                        )
                      })}
                    </>
                  )
                })}
              </div>
            </div>
          </div>
        </div>
        {selectedDate && (
          <div className="events-panel min-w-[260px] w-[420px] p-6 bg-transparent flex flex-col border-l">
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
            <div className="flex-1 overflow-auto no-scrollbar space-y-3">
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
              {/* Dynamic bottom border positioned 10px below last line/content */}
              <div className="h-2.5" />
              <div className="events-divider border-b" />
            </div>
          </div>
        )}
      </div>
      <EventModal event={editingEvent} isOpen={isEventModalOpen} onOpenChange={setIsEventModalOpen} onSave={handleSaveEvent} onDelete={handleDeleteEvent} selectedDate={selectedDate} />
    </div>
  )
}
