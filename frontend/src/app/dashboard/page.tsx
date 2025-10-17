"use client"

import { useEffect, useState } from "react"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { Button } from "@/components/ui/button"
import { DollarSign, Users, CheckCircle, Star, Plus, FileText, BarChart as BarChartIcon, UserPlus, LogOut } from "lucide-react"
import { cn } from "@/lib/utils"
import { supabase } from "@/lib/supabase"
import { useRouter } from "next/navigation"
import { toast } from "sonner"

type Activity = { 
  id: string
  title: string
  priority: 'low' | 'medium' | 'high'
  time: string 
}

export default function DashboardPage() {
  const router = useRouter()
  const [user, setUser] = useState<any>(null)
  const [activities, setActivities] = useState<Activity[]>([])
  const [loading, setLoading] = useState(true)

  useEffect(() => {
    const checkUser = async () => {
      const { data: { session } } = await supabase.auth.getSession()
      
      if (!session) {
        router.push('/login')
        return
      }
      
      setUser(session.user)
      setLoading(false)
    }

    checkUser()

    const { data: { subscription } } = supabase.auth.onAuthStateChange((_event, session) => {
      if (!session) {
        router.push('/login')
      } else {
        setUser(session.user)
      }
    })

    return () => subscription.unsubscribe()
  }, [router])

  const handleSignOut = async () => {
    await supabase.auth.signOut()
    toast.success("Signed out successfully")
    router.push('/login')
  }

  const kpis = [
    { id: 'revenue', title: 'Revenue', value: '$0', icon: DollarSign, color: 'text-green-600' },
    { id: 'customers', title: 'New Customers', value: '0', icon: Users, color: 'text-blue-600' },
    { id: 'tasks', title: 'Tasks Completed', value: '0', icon: CheckCircle, color: 'text-purple-600' },
    { id: 'satisfaction', title: 'Satisfaction', value: '0%', icon: Star, color: 'text-yellow-600' },
  ]

  const quickActions = [
    { id: 'qa1', label: 'New Invoice', icon: FileText, color: 'blue' },
    { id: 'qa2', label: 'Add Customer', icon: UserPlus, color: 'green' },
    { id: 'qa3', label: 'Create Task', icon: Plus, color: 'purple' },
    { id: 'qa4', label: 'Report', icon: BarChartIcon, color: 'orange' },
  ]

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-lg">Loading...</div>
      </div>
    )
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-slate-50 via-white to-blue-50 dark:from-slate-950 dark:via-slate-900 dark:to-blue-950">
      <header className="border-b bg-white/50 dark:bg-slate-900/50 backdrop-blur-sm sticky top-0 z-10">
        <div className="container mx-auto px-4 py-4 flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent">
              Imperecta
            </h1>
            <p className="text-sm text-muted-foreground">
              Welcome back, {user?.user_metadata?.name || user?.email}
            </p>
          </div>
          <Button variant="outline" onClick={handleSignOut}>
            <LogOut className="mr-2 h-4 w-4" />
            Sign Out
          </Button>
        </div>
      </header>

      <main className="container mx-auto px-4 py-6">
        <div className="grid grid-cols-1 xl:grid-cols-4 gap-6 items-start">
          <div className="xl:col-span-3 space-y-6">
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {kpis.map(k => (
                <Card key={k.id} className="hover:shadow-lg transition-shadow">
                  <CardHeader className="flex flex-row items-center justify-between pb-2">
                    <CardTitle className="text-sm font-medium">{k.title}</CardTitle>
                    <k.icon className={cn("h-5 w-5 opacity-70", k.color)} />
                  </CardHeader>
                  <CardContent>
                    <div className="text-2xl font-bold">{k.value}</div>
                  </CardContent>
                </Card>
              ))}
            </div>
          </div>

          <div className="xl:col-span-1 space-y-6">
            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader className="py-4">
                <CardTitle>Quick Actions</CardTitle>
              </CardHeader>
              <CardContent className="p-4">
                <div className="grid grid-cols-2 gap-3">
                  {quickActions.map(a => (
                    <Button 
                      key={a.id} 
                      variant="outline" 
                      className="h-20 flex-col gap-2 text-xs hover:bg-primary/10"
                    >
                      <div className={cn("p-2 rounded-lg bg-primary/10")}>
                        <a.icon className="h-5 w-5" />
                      </div>
                      <span>{a.label}</span>
                    </Button>
                  ))}
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader className="py-4">
                <CardTitle>Recent Activities</CardTitle>
              </CardHeader>
              <CardContent className="p-4 min-h-[300px]">
                <div className="space-y-3">
                  {activities.length === 0 ? (
                    <p className="text-sm text-muted-foreground text-center py-8">
                      No recent activities
                    </p>
                  ) : (
                    activities.map(act => (
                      <div key={act.id} className="flex items-start gap-3 p-3 hover:bg-muted/40 rounded-lg transition-colors">
                        <div className={cn(
                          "w-2 h-2 rounded-full mt-2", 
                          act.priority === 'high' ? 'bg-orange-500' : 
                          act.priority === 'medium' ? 'bg-blue-500' : 
                          'bg-gray-400'
                        )} />
                        <div className="flex-1 min-w-0">
                          <p className="font-medium text-sm truncate">{act.title}</p>
                          <p className="text-xs text-muted-foreground mt-1">{act.time}</p>
                        </div>
                      </div>
                    ))
                  )}
                </div>
              </CardContent>
            </Card>

            <Card className="hover:shadow-lg transition-shadow">
              <CardHeader className="py-4">
                <CardTitle>AI Insights</CardTitle>
              </CardHeader>
              <CardContent className="p-4 text-sm text-muted-foreground">
                <p className="text-center py-4">Coming soon...</p>
              </CardContent>
            </Card>
          </div>
        </div>
      </main>
    </div>
  )
}

