import { drizzle } from 'drizzle-orm/postgres-js'
import postgres from 'postgres'
import { config } from 'dotenv'

// Load environment variables
config()

const connectionString = process.env.DATABASE_URL || 'postgresql://postgres:wolf155@localhost:5432/imperecta_db'

// Create postgres connection
const client = postgres(connectionString, {
  max: 10,
  idle_timeout: 20,
  connect_timeout: 10,
})

// Create drizzle instance
export const db = drizzle(client)

// Export client for manual operations if needed
export { client } 