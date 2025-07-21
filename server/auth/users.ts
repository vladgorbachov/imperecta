/**
 * Server-side user management
 */

import type { User } from './types'

// Test users for development
export const testUsers: User[] = [
  {
    id: "1",
    name: "Admin User",
    email: "admin@example.com",
    password: "admin123",
    position: "System Administrator",
    department: "IT",
    avatar: "/placeholder-user.jpg",
    role: "admin",
    createdAt: new Date("2024-01-01"),
    updatedAt: new Date("2024-01-01"),
  },
  {
    id: "2",
    name: "Manager User",
    email: "manager@example.com",
    password: "manager123",
    position: "Project Manager",
    department: "Management",
    avatar: "/placeholder-user.jpg",
    role: "manager",
    createdAt: new Date("2024-01-01"),
    updatedAt: new Date("2024-01-01"),
  },
  {
    id: "3",
    name: "Employee User",
    email: "employee@example.com",
    password: "employee123",
    position: "Software Developer",
    department: "Engineering",
    avatar: "/placeholder-user.jpg",
    role: "employee",
    createdAt: new Date("2024-01-01"),
    updatedAt: new Date("2024-01-01"),
  },
]

/**
 * Find user by email and password
 */
export function findUserByCredentials(email: string, password: string): User | null {
  const user = testUsers.find(
    (u) => u.email === email && u.password === password
  )
  
  if (!user) {
    return null
  }
  
  // Return user without password
  const { password: _, ...userWithoutPassword } = user
  return userWithoutPassword as User
}

/**
 * Find user by ID
 */
export function findUserById(id: string): User | null {
  const user = testUsers.find((u) => u.id === id)
  
  if (!user) {
    return null
  }
  
  // Return user without password
  const { password: _, ...userWithoutPassword } = user
  return userWithoutPassword as User
}

/**
 * Get all users (without passwords)
 */
export function getAllUsers(): Omit<User, 'password'>[] {
  return testUsers.map(({ password: _, ...user }) => user)
} 