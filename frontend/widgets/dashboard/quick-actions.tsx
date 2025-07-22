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
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent text-2xl">
          Quick Actions
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-y-auto max-h-96 pr-2">
        <div className="grid grid-cols-1 gap-4">
          {actions.map((action) => (
            <Button
              key={action.id}
              variant="ghost"
              className="glass rounded-xl p-4 h-auto hover:scale-105 justify-start"
            >
              <div className={`w-12 h-12 rounded-lg ${action.color} flex items-center justify-center mr-3`}>
                <action.icon className="h-6 w-6 text-white" />
              </div>
              <div className="text-left">
                <div className="font-medium text-lg">{action.title}</div>
                <div className="text-base text-muted-foreground">{action.description}</div>
              </div>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
