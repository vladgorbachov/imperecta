import { Router } from 'express'
import { createUser, getUserById, getUserBySupabaseId, getAllUsers, updateUser, deleteUser } from '../database'
import { db } from '../connection'
import { and, eq } from 'drizzle-orm'
import { calendarEvents, users as usersTable } from '../schema'

const router = Router()

// Get all users
router.get('/', async (req, res) => {
  try {
    const users = await getAllUsers()
    res.json(users)
  } catch (error) {
    res.status(500).json({ error: 'Failed to get users' })
  }
})

// Get user by ID
router.get('/:id', async (req, res) => {
  try {
    const user = await getUserById(req.params.id)
    if (!user) {
      return res.status(404).json({ error: 'User not found' })
    }
    res.json(user)
  } catch (error) {
    res.status(500).json({ error: 'Failed to get user' })
  }
})

// Get user by Supabase ID
router.get('/supabase/:supabaseId', async (req, res) => {
  try {
    const user = await getUserBySupabaseId(req.params.supabaseId)
    if (!user) {
      return res.status(404).json({ error: 'User not found' })
    }
    res.json(user)
  } catch (error) {
    res.status(500).json({ error: 'Failed to get user' })
  }
})

// Create user
router.post('/', async (req, res) => {
  try {
    const user = await createUser(req.body)
    if (!user) {
      return res.status(400).json({ error: 'Failed to create user' })
    }
    res.status(201).json(user)
  } catch (error) {
    res.status(500).json({ error: 'Failed to create user' })
  }
})

// Update user
router.put('/:id', async (req, res) => {
  try {
    const user = await updateUser(req.params.id, req.body)
    if (!user) {
      return res.status(404).json({ error: 'User not found' })
    }
    res.json(user)
  } catch (error) {
    res.status(500).json({ error: 'Failed to update user' })
  }
})

// Delete user
router.delete('/:id', async (req, res) => {
  try {
    const success = await deleteUser(req.params.id)
    if (!success) {
      return res.status(404).json({ error: 'User not found' })
    }
    res.status(204).send()
  } catch (error) {
    res.status(500).json({ error: 'Failed to delete user' })
  }
})

export default router 

// Calendar events CRUD scoped to current user
router.get('/:id/events', async (req, res) => {
  try {
    const userId = req.params.id
    const events = await db.select().from(calendarEvents).where(eq(calendarEvents.user_id, userId))
    res.json(events)
  } catch {
    res.status(500).json({ error: 'Failed to fetch events' })
  }
})

router.post('/:id/events', async (req, res) => {
  try {
    const userId = req.params.id
    const { id, title, description, start_at, end_at, location, type, color, attendees } = req.body || {}
    if (!title || !start_at) return res.status(400).json({ error: 'title and start_at required' })
    const [created] = await db.insert(calendarEvents).values({
      id,
      user_id: userId,
      title,
      description,
      start_at: new Date(start_at),
      end_at: end_at ? new Date(end_at) : null,
      location,
      type,
      color,
      attendees: attendees ? JSON.stringify(attendees) : null,
    }).returning()
    res.status(201).json(created)
  } catch (e) {
    res.status(500).json({ error: 'Failed to create event' })
  }
})

router.put('/:id/events/:eventId', async (req, res) => {
  try {
    const userId = req.params.id
    const eventId = req.params.eventId
    const { title, description, start_at, end_at, location, type, color, attendees } = req.body || {}
    const [updated] = await db.update(calendarEvents).set({
      title,
      description,
      start_at: start_at ? new Date(start_at) : undefined,
      end_at: end_at ? new Date(end_at) : undefined,
      location,
      type,
      color,
      attendees: attendees ? JSON.stringify(attendees) : undefined,
      updated_at: new Date(),
    }).where(and(eq(calendarEvents.id, eventId), eq(calendarEvents.user_id, userId))).returning()
    if (!updated) return res.status(404).json({ error: 'Event not found' })
    res.json(updated)
  } catch {
    res.status(500).json({ error: 'Failed to update event' })
  }
})

router.delete('/:id/events/:eventId', async (req, res) => {
  try {
    const userId = req.params.id
    const eventId = req.params.eventId
    const deleted = await db.delete(calendarEvents).where(and(eq(calendarEvents.id, eventId), eq(calendarEvents.user_id, userId)))
    if ((deleted as any).rowCount === 0) return res.status(404).json({ error: 'Event not found' })
    res.status(204).send()
  } catch {
    res.status(500).json({ error: 'Failed to delete event' })
  }
})