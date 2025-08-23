import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { Plus, FileText, Users, Calendar, Settings } from "lucide-react"

export function QuickActions() {
  // const { t } = useLanguage()

  const actions = [
    {
      id: 1,
      title: "New Project",
      description: "Create a new project",
      icon: Plus,
      color: "bg-gradient-to-r from-blue-500 to-blue-600",
    },
    {
      id: 2,
      title: "New Task",
      description: "Add a new task",
      icon: FileText,
      color: "bg-gradient-to-r from-green-500 to-green-600",
    },
    {
      id: 3,
      title: "Add Team Member",
      description: "Invite new member",
      icon: Users,
      color: "bg-gradient-to-r from-purple-500 to-purple-600",
    },
    {
      id: 4,
      title: "Schedule Meeting",
      description: "Book a meeting",
      icon: Calendar,
      color: "bg-gradient-to-r from-orange-500 to-orange-600",
    },
    {
      id: 5,
      title: "Settings",
      description: "Configure system",
      icon: Settings,
      color: "bg-gradient-to-r from-gray-500 to-gray-600",
    },
  ]

  return (
    <Card className="glass-card h-full border-cyan-400/50">
      <CardHeader className="pb-4">
        <CardTitle className="text-2xl dark:text-white">Quick actions</CardTitle>
      </CardHeader>
      <CardContent className="pr-2">
        <div className="grid grid-cols-2 gap-3 md:grid-cols-2">
          {actions.map((action) => (
            <Button
              key={action.id}
              variant="ghost"
              className="glass rounded-xl h-16 px-3 hover:scale-[1.02] justify-start dark:neon-glow"
            >
              <div className={`w-8 h-8 md:w-9 md:h-9 rounded-md ${action.color} flex items-center justify-center mr-3`}>
                <action.icon className="h-4 w-4 md:h-5 md:w-5 text-white" />
              </div>
              <div className="text-left leading-tight">
                <div className="font-medium text-sm md:text-base">{action.title}</div>
                <div className="text-xs md:text-sm text-muted-foreground">{action.description}</div>
              </div>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
