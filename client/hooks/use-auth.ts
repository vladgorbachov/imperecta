'use client'

import { useSession, signIn, signOut, getSession } from 'next-auth/react'
import { useRouter } from 'next/navigation'
import { useCallback } from 'react'

export function useAuth() {
  const { data: session, status, update } = useSession()
  const router = useRouter()

  const login = useCallback(async (email: string, password: string) => {
    try {
      const result = await signIn('credentials', {
        email,
        password,
        redirect: false,
      })

      if (result?.error) {
        throw new Error(result.error)
      }

      return result
    } catch (error) {
      console.error('Login error:', error)
      throw error
    }
  }, [])

  const loginWithProvider = useCallback(async (provider: string) => {
    try {
      await signIn(provider, { callbackUrl: '/' })
    } catch (error) {
      console.error(`Login with ${provider} error:`, error)
      throw error
    }
  }, [])

  const logout = useCallback(async () => {
    try {
      await signOut({ redirect: false })
      router.push('/login')
    } catch (error) {
      console.error('Logout error:', error)
      throw error
    }
  }, [router])

  const refreshSession = useCallback(async () => {
    try {
      await update()
    } catch (error) {
      console.error('Session refresh error:', error)
      throw error
    }
  }, [update])

  const checkAuth = useCallback(async () => {
    try {
      const session = await getSession()
      return session
    } catch (error) {
      console.error('Check auth error:', error)
      return null
    }
  }, [])

  return {
    session,
    status,
    isAuthenticated: status === 'authenticated',
    isLoading: status === 'loading',
    login,
    loginWithProvider,
    logout,
    refreshSession,
    checkAuth,
  }
} 