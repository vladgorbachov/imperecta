import { defineConfig } from 'drizzle-kit'

export default defineConfig({
  schema: './src/api/schema.ts',
  out: './database/migrations',
  dialect: 'postgresql',
  dbCredentials: {
    url: process.env.DATABASE_URL || 'postgresql://postgres:wolf155@localhost:5432/imperecta_db',
  },
  verbose: true,
  strict: true,
}) 