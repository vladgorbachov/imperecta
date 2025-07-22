import { Router } from 'express'
import { createUser, getUserById, getUserBySupabaseId, getAllUsers, updateUser, deleteUser } from '../database'

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