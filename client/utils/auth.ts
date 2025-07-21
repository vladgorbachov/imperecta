/**
 * Client-side authentication utilities
 */

import type { ClientUser, LoginCredentials } from '../types/auth'

/**
 * Validate login credentials
 */
export function validateCredentials(credentials: LoginCredentials): { isValid: boolean; errors: string[] } {
  const errors: string[] = []

  if (!credentials.email) {
    errors.push('Email is required')
  } else if (!isValidEmail(credentials.email)) {
    errors.push('Invalid email format')
  }

  if (!credentials.password) {
    errors.push('Password is required')
  } else if (credentials.password.length < 6) {
    errors.push('Password must be at least 6 characters')
  }

  return {
    isValid: errors.length === 0,
    errors
  }
}

/**
 * Validate email format
 */
function isValidEmail(email: string): boolean {
  const emailRegex = /^[^\s@]+@[^\s@]+\.[^\s@]+$/
  return emailRegex.test(email)
}

/**
 * Format user display name
 */
export function formatUserName(user: ClientUser): string {
  return user.name || user.email.split('@')[0]
}

/**
 * Get user initials for avatar
 */
export function getUserInitials(user: ClientUser): string {
  if (!user.name) {
    return user.email.charAt(0).toUpperCase()
  }
  
  return user.name
    .split(' ')
    .map(name => name.charAt(0))
    .join('')
    .toUpperCase()
    .slice(0, 2)
}

/**
 * Check if user has specific role
 */
export function hasRole(user: ClientUser, role: ClientUser['role']): boolean {
  return user.role === role
}

/**
 * Check if user has admin privileges
 */
export function isAdmin(user: ClientUser): boolean {
  return user.role === 'admin'
}

/**
 * Check if user has manager privileges
 */
export function isManager(user: ClientUser): boolean {
  return user.role === 'manager' || user.role === 'admin'
} 