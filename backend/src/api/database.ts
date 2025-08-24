import { eq, sql } from 'drizzle-orm'
import { db } from './connection'
import { users, userSettings } from './schema'
import { DatabaseUser, CreateUserRequest, UpdateUserRequest } from './types'

// Test database connection
export const testConnection = async (): Promise<boolean> => {
  try {
    await db.execute(sql`SELECT NOW()`)
    console.log('Database connection successful')
    return true
  } catch (error) {
    console.error('Database connection failed:', error)
    return false
  }
}

// Helper function to convert Drizzle result to DatabaseUser
const convertToDatabaseUser = (user: any): DatabaseUser => ({
  id: user.id,
  supabase_user_id: user.supabase_user_id,
  first_name: user.first_name,
  last_name: user.last_name,
  middle_name: user.middle_name,
  email: user.email,
  phone: user.phone,
  avatar_url: user.avatar_url,
  created_at: user.created_at.toISOString(),
  updated_at: user.updated_at.toISOString(),
})

// User operations
export const createUser = async (userData: CreateUserRequest): Promise<DatabaseUser | null> => {
  try {
    const { supabase_user_id, first_name, last_name, middle_name, email, phone } = userData
    
    const [newUser] = await db.insert(users).values({
      supabase_user_id,
      first_name,
      last_name,
      middle_name,
      email,
      phone,
    }).returning()
    
    return convertToDatabaseUser(newUser)
  } catch (error) {
    console.error('Error creating user:', error)
    return null
  }
}

export const getUserById = async (id: string): Promise<DatabaseUser | null> => {
  try {
    const [user] = await db.select().from(users).where(eq(users.id, id))
    return user ? convertToDatabaseUser(user) : null
  } catch (error) {
    console.error('Error getting user by ID:', error)
    return null
  }
}

export const getUserBySupabaseId = async (supabase_user_id: string): Promise<DatabaseUser | null> => {
  try {
    const [user] = await db.select().from(users).where(eq(users.supabase_user_id, supabase_user_id))
    return user ? convertToDatabaseUser(user) : null
  } catch (error) {
    console.error('Error getting user by Supabase ID:', error)
    return null
  }
}

export const getUserByEmail = async (email: string): Promise<DatabaseUser | null> => {
  try {
    const [user] = await db.select().from(users).where(eq(users.email, email))
    return user ? convertToDatabaseUser(user) : null
  } catch (error) {
    console.error('Error getting user by email:', error)
    return null
  }
}

export const updateUser = async (id: string, userData: UpdateUserRequest): Promise<DatabaseUser | null> => {
  try {
    const { first_name, last_name, middle_name, phone, avatar_url } = userData
    
    const [updatedUser] = await db.update(users)
      .set({
        first_name: first_name || undefined,
        last_name: last_name || undefined,
        middle_name: middle_name || undefined,
        phone: phone || undefined,
        // Allow explicit clearing of avatar_url when empty string provided
        avatar_url: avatar_url === '' ? null : (avatar_url || undefined),
        updated_at: new Date(),
      })
      .where(eq(users.id, id))
      .returning()
    
    return updatedUser ? convertToDatabaseUser(updatedUser) : null
  } catch (error) {
    console.error('Error updating user:', error)
    return null
  }
}

export const deleteUser = async (id: string): Promise<boolean> => {
  try {
    const result = await db.delete(users).where(eq(users.id, id))
    return result.length > 0
  } catch (error) {
    console.error('Error deleting user:', error)
    return false
  }
}

export const getAllUsers = async (): Promise<DatabaseUser[]> => {
  try {
    const allUsers = await db.select().from(users).orderBy(users.created_at)
    return allUsers.map(convertToDatabaseUser)
  } catch (error) {
    console.error('Error getting all users:', error)
    return []
  }
}

// User settings operations
export const createUserSettings = async (userId: string) => {
  try {
    const [settings] = await db.insert(userSettings).values({
      user_id: userId,
      theme: 'system',
      language: 'en',
      notifications_email: true,
      notifications_push: true,
      notifications_sms: false,
      privacy_profile_visible: true,
      privacy_activity_visible: true,
    }).returning()
    
    return settings
  } catch (error) {
    console.error('Error creating user settings:', error)
    return null
  }
}

export const getUserSettings = async (userId: string) => {
  try {
    const [settings] = await db.select().from(userSettings).where(eq(userSettings.user_id, userId))
    return settings
  } catch (error) {
    console.error('Error getting user settings:', error)
    return null
  }
}

export const updateUserSettings = async (userId: string, settings: any) => {
  try {
    const [updatedSettings] = await db.update(userSettings)
      .set({
        ...settings,
        updated_at: new Date(),
      })
      .where(eq(userSettings.user_id, userId))
      .returning()
    
    return updatedSettings
  } catch (error) {
    console.error('Error updating user settings:', error)
    return null
  }
}

// Close database connection
export const closeConnection = async (): Promise<void> => {
  // Drizzle handles connection pooling automatically
  // No need to manually close connections
} 