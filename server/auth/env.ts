/**
 * Server-side environment variables validation for NextAuth
 */

export const authEnv = {
  NEXTAUTH_URL: process.env.NEXTAUTH_URL,
  NEXTAUTH_SECRET: process.env.NEXTAUTH_SECRET,
  NODE_ENV: process.env.NODE_ENV,
  
  // OAuth providers
  GOOGLE_CLIENT_ID: process.env.GOOGLE_CLIENT_ID,
  GOOGLE_CLIENT_SECRET: process.env.GOOGLE_CLIENT_SECRET,
  GITHUB_CLIENT_ID: process.env.GITHUB_CLIENT_ID,
  GITHUB_CLIENT_SECRET: process.env.GITHUB_CLIENT_SECRET,
  
  // Email configuration
  EMAIL_SERVER_HOST: process.env.EMAIL_SERVER_HOST,
  EMAIL_SERVER_PORT: process.env.EMAIL_SERVER_PORT,
  EMAIL_SERVER_USER: process.env.EMAIL_SERVER_USER,
  EMAIL_SERVER_PASSWORD: process.env.EMAIL_SERVER_PASSWORD,
  EMAIL_FROM: process.env.EMAIL_FROM,
  
  // Database
  DATABASE_URL: process.env.DATABASE_URL,
}

/**
 * Validate required environment variables
 */
export function validateAuthEnv() {
  const required = ['NEXTAUTH_URL', 'NEXTAUTH_SECRET']
  const missing = required.filter(key => !authEnv[key as keyof typeof authEnv])
  
  if (missing.length > 0) {
    throw new Error(`Missing required environment variables: ${missing.join(', ')}`)
  }
  
  // Validate NEXTAUTH_SECRET length
  if (authEnv.NEXTAUTH_SECRET && authEnv.NEXTAUTH_SECRET.length < 32) {
    console.warn('Warning: NEXTAUTH_SECRET should be at least 32 characters long')
  }
  
  return true
}

/**
 * Check if OAuth providers are configured
 */
export function getConfiguredProviders(): string[] {
  const providers: string[] = []
  
  if (authEnv.GOOGLE_CLIENT_ID && authEnv.GOOGLE_CLIENT_SECRET) {
    providers.push('google')
  }
  
  if (authEnv.GITHUB_CLIENT_ID && authEnv.GITHUB_CLIENT_SECRET) {
    providers.push('github')
  }
  
  if (authEnv.EMAIL_SERVER_HOST && authEnv.EMAIL_SERVER_USER && authEnv.EMAIL_SERVER_PASSWORD) {
    providers.push('email')
  }
  
  return providers
}

/**
 * Get environment-specific configuration
 */
export function getAuthConfig() {
  const isDevelopment = authEnv.NODE_ENV === 'development'
  
  return {
    isDevelopment,
    isProduction: authEnv.NODE_ENV === 'production',
    debug: isDevelopment,
    providers: getConfiguredProviders(),
  }
} 