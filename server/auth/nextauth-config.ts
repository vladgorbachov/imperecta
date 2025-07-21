/**
 * Server-side NextAuth configuration
 */

import type { NextAuthOptions } from "next-auth"
import type { JWT } from "next-auth/jwt"
import CredentialsProvider from "next-auth/providers/credentials"
import GoogleProvider from "next-auth/providers/google"
import GitHubProvider from "next-auth/providers/github"
import EmailProvider from "next-auth/providers/email"
import { validateAuthEnv, authEnv } from './env'
import { findUserByCredentials } from './users'
import type { User, AuthSession, AuthToken } from './types'

// Validate environment variables on startup
try {
  validateAuthEnv()
} catch (error) {
  console.error('NextAuth environment validation failed:', error)
}

export const authOptions: NextAuthOptions = {
  providers: [
    // Credentials provider for email/password login
    CredentialsProvider({
      name: "Credentials",
      credentials: {
        email: { label: "Email", type: "email" },
        password: { label: "Password", type: "password" },
      },
      async authorize(credentials) {
        if (!credentials) {
          return null
        }

        const user = findUserByCredentials(credentials.email, credentials.password)

        if (user) {
          return user
        } else {
          return null
        }
      },
    }),
    
    // Google OAuth provider (configured via environment variables)
    ...(authEnv.GOOGLE_CLIENT_ID && authEnv.GOOGLE_CLIENT_SECRET ? [
      GoogleProvider({
        clientId: authEnv.GOOGLE_CLIENT_ID,
        clientSecret: authEnv.GOOGLE_CLIENT_SECRET,
      })
    ] : []),
    
    // GitHub OAuth provider (configured via environment variables)
    ...(authEnv.GITHUB_CLIENT_ID && authEnv.GITHUB_CLIENT_SECRET ? [
      GitHubProvider({
        clientId: authEnv.GITHUB_CLIENT_ID,
        clientSecret: authEnv.GITHUB_CLIENT_SECRET,
      })
    ] : []),
    
    // Email provider for magic links (configured via environment variables)
    ...(authEnv.EMAIL_SERVER_HOST && authEnv.EMAIL_SERVER_USER && authEnv.EMAIL_SERVER_PASSWORD ? [
      EmailProvider({
        server: {
          host: authEnv.EMAIL_SERVER_HOST,
          port: parseInt(authEnv.EMAIL_SERVER_PORT || '587'),
          auth: {
            user: authEnv.EMAIL_SERVER_USER,
            pass: authEnv.EMAIL_SERVER_PASSWORD,
          },
        },
        from: authEnv.EMAIL_FROM || 'noreply@yourdomain.com',
      })
    ] : []),
  ],
  session: {
    strategy: "jwt",
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  jwt: {
    maxAge: 30 * 24 * 60 * 60, // 30 days
  },
  callbacks: {
    async jwt({ token, user, account }) {
      // On sign-in, the `user` object is available.
      if (user) {
        const appUser = user as User
        token.id = appUser.id
        token.position = appUser.position
        token.department = appUser.department
        token.avatar = appUser.avatar
        // The default JWT token has `name`, `email`, `picture`. Let's keep them.
        token.picture = appUser.avatar
      }
      
      // Handle OAuth account linking
      if (account) {
        token.provider = account.provider
      }
      
      return token
    },
    async session({ session, token }: { session: AuthSession; token: AuthToken }) {
      // Add data from the token to the session object
      if (session.user && token.id) {
        session.user.id = token.id
        session.user.position = token.position
        session.user.department = token.department
        session.user.avatar = token.avatar
        // `image` is the default property for avatar in session.user
        session.user.image = token.picture
      }
      return session
    },
    async redirect({ url, baseUrl }) {
      // Allows relative callback URLs
      if (url.startsWith("/")) return `${baseUrl}${url}`
      // Allows callback URLs on the same origin
      else if (new URL(url).origin === baseUrl) return url
      return baseUrl
    },
  },
  pages: {
    signIn: "/login",
    signOut: "/auth/signout",
    error: "/auth/error",
    verifyRequest: "/auth/verify-request",
    newUser: "/auth/new-user",
  },
  secret: authEnv.NEXTAUTH_SECRET,
  debug: authEnv.NODE_ENV === "development",
} 