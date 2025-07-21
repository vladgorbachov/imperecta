/**
 * Client-side authentication providers utility
 */

/**
 * Get configured OAuth providers from environment
 * This is a client-safe version that doesn't expose sensitive data
 */
export function getConfiguredProviders(): string[] {
  // In a real app, this would come from an API endpoint
  // For now, we'll return an empty array since we can't access server env vars from client
  return []
}

/**
 * Check if a specific provider is configured
 */
export function isProviderConfigured(provider: string): boolean {
  return getConfiguredProviders().includes(provider)
} 