import { useState, useEffect } from "react"
import { useNavigate, Outlet } from "react-router-dom"
import { Sidebar } from "@/widgets/sidebar/sidebar"
import { Header } from "@/widgets/header/header"
import { Skeleton } from "@/shared/components/ui/skeleton"
import { useSupabase } from "@/shared/contexts/supabase-context"

export default function DashboardLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false)
  const navigate = useNavigate()
  const { user, loading } = useSupabase()

  useEffect(() => {
    if (!loading && !user) {
      navigate("/login")
    }
  }, [user, loading, navigate])

  if (loading) {
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

  if (!user) {
    return null
  }

  return (
    <div className="flex h-screen overflow-hidden bg-gradient-to-br from-blue-50 via-white to-purple-50 dark:from-blue-950 dark:via-slate-900 dark:to-purple-950">
      <Sidebar open={sidebarOpen} onOpenChange={setSidebarOpen} />
      <div className="flex flex-1 flex-col overflow-hidden">
        <Header onMenuButtonClick={() => setSidebarOpen(true)} />
        <main className="flex-1 overflow-auto pr-5 pl-6 pt-6 pb-6">
          <div className="w-full">
            <Outlet />
          </div>
        </main>
      </div>
    </div>
  )
} 