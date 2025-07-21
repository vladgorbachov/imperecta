/**
 * Server-side authentication types
 */

import type { User as NextAuthUser, Session as NextAuthSession } from 'next-auth'
import type { JWT as NextAuthJWT } from 'next-auth/jwt'

export interface User extends NextAuthUser {
  id: string
  name: string
  email: string
  password?: string
  position: string
  department: string
  avatar: string
  role: 'admin' | 'manager' | 'employee'
  createdAt: Date
  updatedAt: Date
}

export interface AuthSession extends NextAuthSession {
  user: {
    id: string
    name: string
    email: string
    position: string
    department: string
    avatar: string
    image: string
  }
  expires: string
}

export interface AuthToken extends NextAuthJWT {
  id: string
  position: string
  department: string
  avatar: string
  picture: string
  provider?: string
}

export interface AuthProvider {
  id: string
  name: string
  type: 'oauth' | 'email' | 'credentials'
  enabled: boolean
} 