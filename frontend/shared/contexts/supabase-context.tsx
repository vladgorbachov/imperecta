import { createContext, useContext, useEffect, useState, type ReactNode } from 'react'
import { User, Session, AuthError } from '@supabase/supabase-js'
import { supabase } from '@/app/main'

// Types for database user (will be fetched from API)
interface DatabaseUser {
  id: string
  supabase_user_id: string
  first_name: string
  last_name: string
  middle_name?: string
  email: string
  phone?: string
  avatar_url?: string
  created_at: string
  updated_at: string
}

interface CreateUserRequest {
  supabase_user_id: string
  first_name: string
  last_name: string
  middle_name?: string
  email: string
  phone?: string
}

interface SupabaseContextType {
  user: User | null
  session: Session | null
  loading: boolean
  databaseUser: DatabaseUser | null
  signIn: (email: string, password: string) => Promise<{ error: AuthError | null }>
  signUp: (email: string, password: string, metadata?: { name?: string; first_name?: string; last_name?: string; middle_name?: string; phone?: string }) => Promise<{ error: AuthError | null }>
  signOut: () => Promise<{ error: AuthError | null }>
  resetPassword: (email: string) => Promise<{ error: AuthError | null }>
  updateProfile: (updates: { name?: string; avatar_url?: string }) => Promise<{ error: AuthError | null }>
}

const SupabaseContext = createContext<SupabaseContextType | undefined>(undefined)

interface SupabaseProviderProps {
  children: ReactNode
}

export function SupabaseProvider({ children }: SupabaseProviderProps) {
  const [user, setUser] = useState<User | null>(null)
  const [session, setSession] = useState<Session | null>(null)
  const [loading, setLoading] = useState(true)
  const [databaseUser, setDatabaseUser] = useState<DatabaseUser | null>(null)

  // Load database user when Supabase user changes
  useEffect(() => {
    const loadDatabaseUser = async (supabaseUser: User) => {
      try {
        // Try to get existing user from API
        const response = await fetch(`/api/users/supabase/${supabaseUser.id}`)
        let dbUser: DatabaseUser | null = null
        
        if (response.ok) {
          dbUser = await response.json()
        } else if (response.status === 404) {
          // If user doesn't exist, create them via API
          const userData: CreateUserRequest = {
            supabase_user_id: supabaseUser.id,
            first_name: supabaseUser.user_metadata?.first_name || supabaseUser.user_metadata?.full_name?.split(' ')[0] || '',
            last_name: supabaseUser.user_metadata?.last_name || supabaseUser.user_metadata?.full_name?.split(' ').slice(1).join(' ') || '',
            middle_name: supabaseUser.user_metadata?.middle_name,
            email: supabaseUser.email || '',
            phone: supabaseUser.user_metadata?.phone
          }
          
          const createResponse = await fetch('/api/users', {
            method: 'POST',
            headers: {
              'Content-Type': 'application/json',
            },
            body: JSON.stringify(userData),
          })
          
          if (createResponse.ok) {
            dbUser = await createResponse.json()
          }
        }
        
        setDatabaseUser(dbUser)
      } catch (error) {
        console.error('Error loading database user:', error)
      }
    }

    if (user) {
      loadDatabaseUser(user)
    } else {
      setDatabaseUser(null)
    }
  }, [user])

  useEffect(() => {
    // Get initial session
    const getInitialSession = async () => {
      try {
        const { data: { session } } = await supabase.auth.getSession()
        setSession(session)
        setUser(session?.user ?? null)
      } catch (error) {
        console.error('Error getting session:', error)
      } finally {
        setLoading(false)
      }
    }

    getInitialSession()

    // Listen for auth changes
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange(async (event, session) => {
      console.log('Auth state changed:', event, session?.user?.email)
      setSession(session)
      setUser(session?.user ?? null)
      setLoading(false)
    })

    return () => subscription.unsubscribe()
  }, [])

  const signIn = async (email: string, password: string) => {
    try {
      const { error } = await supabase.auth.signInWithPassword({
        email,
        password,
      })
      return { error }
    } catch (error) {
      console.error('Sign in error:', error)
      return { error: error as AuthError }
    }
  }

  const signUp = async (email: string, password: string, metadata?: { name?: string; first_name?: string; last_name?: string; middle_name?: string; phone?: string }) => {
    try {
      const { error } = await supabase.auth.signUp({
        email,
        password,
        options: {
          data: metadata
        }
      })
      return { error }
    } catch (error) {
      console.error('Sign up error:', error)
      return { error: error as AuthError }
    }
  }

  const signOut = async () => {
    try {
      const { error } = await supabase.auth.signOut()
      return { error }
    } catch (error) {
      console.error('Sign out error:', error)
      return { error: error as AuthError }
    }
  }

  const resetPassword = async (email: string) => {
    try {
      const { error } = await supabase.auth.resetPasswordForEmail(email, {
        redirectTo: `${window.location.origin}/reset-password`,
      })
      return { error }
    } catch (error) {
      console.error('Reset password error:', error)
      return { error: error as AuthError }
    }
  }

  const updateProfile = async (updates: { name?: string; avatar_url?: string }) => {
    try {
      const { error } = await supabase.auth.updateUser({
        data: updates
      })
      return { error }
    } catch (error) {
      console.error('Update profile error:', error)
      return { error: error as AuthError }
    }
  }

  return (
    <SupabaseContext.Provider
      value={{
        user,
        session,
        loading,
        databaseUser,
        signIn,
        signUp,
        signOut,
        resetPassword,
        updateProfile,
      }}
    >
      {children}
    </SupabaseContext.Provider>
  )
}

export function useSupabase() {
  const context = useContext(SupabaseContext)
  if (context === undefined) {
    throw new Error('useSupabase must be used within a SupabaseProvider')
  }
  return context
} 