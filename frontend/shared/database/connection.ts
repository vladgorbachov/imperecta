import { drizzle } from 'drizzle-orm/postgres-js'
import postgres from 'postgres'
import * as schema from './schema'

// Create postgres connection
const connectionString = import.meta.env.VITE_DATABASE_URL || 'postgresql://postgres:wolf155@localhost:5432/imperecta_db'

const client = postgres(connectionString, {
  max: 10,
  idle_timeout: 20,
  connect_timeout: 10,
})

// Create drizzle instance
export const db = drizzle(client, { schema })

// Test database connection
export const testConnection = async (): Promise<boolean> => {
  try {
    await client`SELECT NOW()`
    console.log('Database connection successful')
    return true
  } catch (error) {
    console.error('Database connection failed:', error)
    return false
  }
}

// Close database connection
export const closeConnection = async (): Promise<void> => {
  await client.end()
} 