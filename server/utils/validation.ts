/**
 * Server-side validation utilities
 */

import type { User } from '../auth/types'

/**
 * Validate user data
 */
export function validateUser(user: Partial<User>): { isValid: boolean; errors: string[] } {
  const errors: string[] = []

  if (!user.email) {
    errors.push('Email is required')
  } else if (!isValidEmail(user.email)) {
    errors.push('Invalid email format')
  }

  if (!user.name) {
    errors.push('Name is required')
  }

  if (!user.role) {
    errors.push('Role is required')
  } else if (!['admin', 'manager', 'employee'].includes(user.role)) {
    errors.push('Invalid role')
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
 * Sanitize user data for client
 */
export function sanitizeUser(user: User): Omit<User, 'password'> {
  const { password: _, ...sanitizedUser } = user
  return sanitizedUser
}

/**
 * Check if user has specific role
 */
export function hasRole(user: User, role: User['role']): boolean {
  return user.role === role
}

/**
 * Check if user has admin privileges
 */
export function isAdmin(user: User): boolean {
  return user.role === 'admin'
}

/**
 * Check if user has manager privileges
 */
export function isManager(user: User): boolean {
  return user.role === 'manager' || user.role === 'admin'
} 