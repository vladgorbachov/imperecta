import { useState, useEffect } from "react"
import { Dialog, DialogContent, DialogHeader, DialogTitle, DialogFooter } from "@/shared/components/ui/dialog"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import { Label } from "@/shared/components/ui/label"
import { Textarea } from "@/shared/components/ui/textarea"
import { Select, SelectContent, SelectItem, SelectTrigger, SelectValue } from "@/shared/components/ui/select"
import { Badge } from "@/shared/components/ui/badge"
import { Calendar } from "@/shared/components/ui/calendar"
import { 
  Plus, 
  Edit, 
  Trash2, 
  Clock, 
  MapPin, 
  Users,
  X
} from "lucide-react"

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

interface EventModalProps {
  event?: Event
  isOpen: boolean
  onOpenChange: (open: boolean) => void
  onSave: (event: Event) => void
  onDelete?: (eventId: string) => void
  selectedDate?: Date | null
}

const eventColors = [
  { value: "bg-blue-500", label: "Blue" },
  { value: "bg-green-500", label: "Green" },
  { value: "bg-purple-500", label: "Purple" },
  { value: "bg-red-500", label: "Red" },
  { value: "bg-orange-500", label: "Orange" },
  { value: "bg-pink-500", label: "Pink" },
]

export function EventModal({ 
  event, 
  isOpen, 
  onOpenChange, 
  onSave, 
  onDelete, 
  selectedDate 
}: EventModalProps) {
  const [formData, setFormData] = useState<Partial<Event>>({
    title: "",
    description: "",
    date: selectedDate || new Date(),
    time: "09:00",
    endTime: "10:00",
    location: "",
    attendees: [],
    type: "meeting",
    color: "bg-blue-500"
  })

  const [newAttendee, setNewAttendee] = useState("")

  useEffect(() => {
    if (event) {
      setFormData(event)
    } else {
      setFormData({
        title: "",
        description: "",
        date: selectedDate || new Date(),
        time: "09:00",
        endTime: "10:00",
        location: "",
        attendees: [],
        type: "meeting",
        color: "bg-blue-500"
      })
    }
  }, [event, selectedDate])

  const handleSave = () => {
    if (!formData.title || !formData.date || !formData.time) return

    const eventData: Event = {
      id: event?.id || Date.now().toString(),
      title: formData.title,
      description: formData.description,
      date: formData.date!,
      time: formData.time,
      endTime: formData.endTime,
      location: formData.location,
      attendees: formData.attendees,
      type: formData.type!,
      color: formData.color
    }

    onSave(eventData)
    onOpenChange(false)
  }

  const handleAddAttendee = () => {
    if (newAttendee.trim()) {
      setFormData(prev => ({
        ...prev,
        attendees: [...(prev.attendees || []), newAttendee.trim()]
      }))
      setNewAttendee("")
    }
  }

  const handleRemoveAttendee = (index: number) => {
    setFormData(prev => ({
      ...prev,
      attendees: prev.attendees?.filter((_, i) => i !== index)
    }))
  }

  const handleDelete = () => {
    if (event && onDelete) {
      onDelete(event.id)
      onOpenChange(false)
    }
  }

  return (
    <Dialog open={isOpen} onOpenChange={onOpenChange}>
      <DialogContent className="dark:neon-glow max-w-4xl max-h-[90vh] overflow-y-auto">
        <DialogHeader>
          <DialogTitle className="dark:gradient-text text-xl">
            {event ? "Edit Event" : "Add New Event"}
          </DialogTitle>
        </DialogHeader>
        
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          {/* Left Column */}
          <div className="space-y-4">
            <div>
              <Label htmlFor="title">Event Title *</Label>
              <Input
                id="title"
                value={formData.title}
                onChange={(e) => setFormData(prev => ({ ...prev, title: e.target.value }))}
                placeholder="Enter event title"
                className="dark:neon-glow"
              />
            </div>

            <div>
              <Label htmlFor="description">Description</Label>
              <Textarea
                id="description"
                value={formData.description}
                onChange={(e) => setFormData(prev => ({ ...prev, description: e.target.value }))}
                placeholder="Enter event description"
                className="dark:neon-glow"
                rows={3}
              />
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label>Event Type</Label>
                <Select value={formData.type} onValueChange={(value) => setFormData(prev => ({ ...prev, type: value as Event['type'] }))}>
                  <SelectTrigger className="dark:neon-glow">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    <SelectItem value="meeting">Meeting</SelectItem>
                    <SelectItem value="deadline">Deadline</SelectItem>
                    <SelectItem value="reminder">Reminder</SelectItem>
                    <SelectItem value="event">Event</SelectItem>
                  </SelectContent>
                </Select>
              </div>

              <div>
                <Label>Color</Label>
                <Select value={formData.color} onValueChange={(value) => setFormData(prev => ({ ...prev, color: value }))}>
                  <SelectTrigger className="dark:neon-glow">
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {eventColors.map((color) => (
                      <SelectItem key={color.value} value={color.value}>
                        <div className="flex items-center gap-2">
                          <div className={`w-4 h-4 rounded-full ${color.value}`} />
                          {color.label}
                        </div>
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
            </div>

            <div className="grid grid-cols-2 gap-4">
              <div>
                <Label htmlFor="time">Start Time *</Label>
                <Input
                  id="time"
                  type="time"
                  value={formData.time}
                  onChange={(e) => setFormData(prev => ({ ...prev, time: e.target.value }))}
                  className="dark:neon-glow"
                />
              </div>

              <div>
                <Label htmlFor="endTime">End Time</Label>
                <Input
                  id="endTime"
                  type="time"
                  value={formData.endTime}
                  onChange={(e) => setFormData(prev => ({ ...prev, endTime: e.target.value }))}
                  className="dark:neon-glow"
                />
              </div>
            </div>

            <div>
              <Label htmlFor="location">Location</Label>
              <Input
                id="location"
                value={formData.location}
                onChange={(e) => setFormData(prev => ({ ...prev, location: e.target.value }))}
                placeholder="Enter location"
                className="dark:neon-glow"
              />
            </div>

            {/* Attendees */}
            <div>
              <Label>Attendees</Label>
              <div className="flex gap-2 mt-2">
                <Input
                  value={newAttendee}
                  onChange={(e) => setNewAttendee(e.target.value)}
                  placeholder="Add attendee"
                  className="dark:neon-glow"
                  onKeyPress={(e) => e.key === 'Enter' && handleAddAttendee()}
                />
                <Button onClick={handleAddAttendee} size="sm" className="dark:neon-glow">
                  <Plus className="h-4 w-4" />
                </Button>
              </div>
              {formData.attendees && formData.attendees.length > 0 && (
                <div className="flex flex-wrap gap-2 mt-2">
                  {formData.attendees.map((attendee, index) => (
                    <Badge key={index} variant="secondary" className="dark:neon-glow">
                      {attendee}
                      <Button
                        variant="ghost"
                        size="sm"
                        className="h-4 w-4 p-0 ml-1"
                        onClick={() => handleRemoveAttendee(index)}
                      >
                        <X className="h-3 w-3" />
                      </Button>
                    </Badge>
                  ))}
                </div>
              )}
            </div>
          </div>

          {/* Right Column */}
          <div className="space-y-4">
            {/* Date Selection */}
            <div>
              <Label>Date</Label>
              <div className="mt-2">
                <Calendar
                  mode="single"
                  selected={formData.date}
                  onSelect={(date) => setFormData(prev => ({ ...prev, date: date || new Date() }))}
                  className="rounded-lg border dark:neon-glow bg-card p-3"
                  classNames={{
                    months: "flex flex-col sm:flex-row space-y-4 sm:space-x-4 sm:space-y-0",
                    month: "space-y-4",
                    caption: "flex justify-center pt-1 relative items-center",
                    caption_label: "text-sm font-medium",
                    nav: "space-x-1 flex items-center",
                    nav_button: "h-7 w-7 bg-transparent p-0 opacity-50 hover:opacity-100 border rounded-md hover:bg-accent",
                    nav_button_previous: "absolute left-1",
                    nav_button_next: "absolute right-1",
                    table: "w-full border-collapse space-y-1",
                    head_row: "flex",
                    head_cell: "text-muted-foreground rounded-md w-9 font-normal text-[0.8rem]",
                    row: "flex w-full mt-2",
                    cell: "text-center text-sm p-0 relative [&:has([aria-selected])]:bg-accent first:[&:has([aria-selected])]:rounded-l-md last:[&:has([aria-selected])]:rounded-r-md focus-within:relative focus-within:z-20",
                    day: "h-9 w-9 p-0 font-normal aria-selected:opacity-100 hover:bg-accent hover:text-accent-foreground rounded-md transition-colors",
                    day_selected: "bg-primary text-primary-foreground hover:bg-primary hover:text-primary-foreground focus:bg-primary focus:text-primary-foreground dark:bg-accent-blue dark:text-white",
                    day_today: "bg-accent text-accent-foreground dark:bg-accent-blue/20 dark:text-accent-blue font-semibold",
                    day_outside: "text-muted-foreground opacity-50",
                    day_disabled: "text-muted-foreground opacity-50",
                    day_range_middle: "aria-selected:bg-accent aria-selected:text-accent-foreground",
                    day_hidden: "invisible",
                  }}
                />
              </div>
            </div>
          </div>
        </div>

        <DialogFooter>
          <div className="flex justify-between w-full">
            {event && onDelete && (
              <Button variant="destructive" onClick={handleDelete} className="dark:neon-glow">
                <Trash2 className="mr-2 h-4 w-4" />
                Delete
              </Button>
            )}
            <div className="flex gap-2">
              <Button variant="outline" onClick={() => onOpenChange(false)} className="dark:neon-glow">
                Cancel
              </Button>
              <Button onClick={handleSave} className="dark:neon-glow">
                {event ? <Edit className="mr-2 h-4 w-4" /> : <Plus className="mr-2 h-4 w-4" />}
                {event ? "Update Event" : "Create Event"}
              </Button>
            </div>
          </div>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  )
} 