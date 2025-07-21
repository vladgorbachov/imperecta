"use client"

import type React from "react"
import { useState } from "react"
import { useRouter } from "next/navigation"
import { Sidebar } from "@/client/components/navigation/sidebar"
import { Header } from "@/client/components/navigation/header"
import { useSession } from "next-auth/react"
import { Skeleton } from "@/client/components/ui/skeleton"

interface DashboardLayoutProps {
  children: React.ReactNode
}

export function DashboardLayout({ children }: DashboardLayoutProps) {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const router = useRouter()

  const { status } = useSession({
    required: true,
    onUnauthenticated() {
      router.push("/login")
    },
  })

  if (status === "loading") {
    return (
      <div className="flex h-screen w-full items-center justify-center bg-gradient-to-br from-blue-50 to-purple-50 dark:from-blue-950 dark:to-purple-950">
        <div className="glass-card">
          <div className="flex items-center gap-4">
            <Skeleton className="h-12 w-12 rounded-full bg-gradient-to-r from-blue-500 to-purple-600" />
            <div className="space-y-2">
              <Skeleton className="h-4 w-32" />
              <Skeleton className="h-3 w-24" />
            </div>
          </div>
        </div>
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-blue-950 dark:via-slate-900 dark:to-purple-950">
      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuButtonClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-auto pr-5 pl-6 pt-6 pb-6">
          <div className="w-full">
            {children}
          </div>
        </main>
      </div>
    </div>
  )
}
