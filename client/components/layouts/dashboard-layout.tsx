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
      <div className="flex h-screen w-full items-center justify-center">
        <Skeleton className="h-12 w-12 rounded-full" />
      </div>
    )
  }

  return (
    <div className="flex h-screen overflow-hidden">
      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuButtonClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-auto">{children}</main>
      </div>
    </div>
  )
}
