export type CalendarBusEvent = {
  id?: string
  title: string
  description?: string
  date: Date
  time?: string
  endTime?: string
  location?: string
  attendees?: string[]
  type?: 'meeting' | 'deadline' | 'reminder' | 'event'
  color?: string
}

export function addCalendarEvent(event: CalendarBusEvent) {
  const detail = {
    ...event,
    id: event.id || `${Date.now()}`,
    type: event.type || 'event',
  }
  window.dispatchEvent(new CustomEvent('imperecta:calendar:add', { detail }))
}


