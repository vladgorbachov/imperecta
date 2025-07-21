/**
 * NextAuth API route handler
 */

import NextAuth from "next-auth"
import { authOptions } from "@/server/auth/nextauth-config"

const handler = NextAuth(authOptions)

export { handler as GET, handler as POST }
