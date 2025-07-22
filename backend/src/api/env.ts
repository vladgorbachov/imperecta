/**
 * Environment variables validation
 */

export const env = {
  NODE_ENV: import.meta.env.MODE,
  VITE_APP_URL: import.meta.env.VITE_APP_URL || 'http://localhost:3000',
  VITE_SUPABASE_URL: import.meta.env.VITE_SUPABASE_URL || '',
  VITE_SUPABASE_ANON_KEY: import.meta.env.VITE_SUPABASE_ANON_KEY || '',
  DATABASE_URL: import.meta.env.VITE_DATABASE_URL || '',
}

/**
 * Validate required environment variables
 */
export function validateEnv() {
  const required = ['VITE_SUPABASE_URL', 'VITE_SUPABASE_ANON_KEY']
  const missing = required.filter(key => !env[key as keyof typeof env])
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`)
  }
  return true
}

/**
 * Get environment-specific configuration
 */
export function getConfig() {
  const isDevelopment = env.NODE_ENV === 'development'
  return {
    isDevelopment,
    isProduction: env.NODE_ENV === 'production',
    debug: isDevelopment,
  }
} 