import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar"

export function AssignedToMe() {
  // const { t } = useLanguage()

  const tasks = [
    {
      id: 1,
      title: "Review project proposal",
      priority: "high",
      assignee: "John Doe",
      avatar: "/placeholder-user.jpg",
      dueDate: "2024-01-15",
    },
    {
      id: 2,
      title: "Update documentation",
      priority: "medium",
      assignee: "Jane Smith",
      avatar: "/placeholder-user.jpg",
      dueDate: "2024-01-20",
    },
    {
      id: 3,
      title: "Code review",
      priority: "low",
      assignee: "Bob Johnson",
      avatar: "/placeholder-user.jpg",
      dueDate: "2024-01-25",
    },
  ]

  const getPriorityColor = (priority: string) => {
    switch (priority) {
      case "high":
        return "bg-red-500"
      case "medium":
        return "bg-yellow-500"
      case "low":
        return "bg-green-500"
      default:
        return "bg-gray-500"
    }
  }

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent text-2xl dark:gradient-text">
          Assigned to Me
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-y-auto max-h-96 pr-2">
        <div className="space-y-4">
          {tasks.map((task) => (
            <div key={task.id} className="glass rounded-xl p-4 hover:scale-105 dark:neon-glow">
              <div className="flex items-start justify-between">
                <div className="flex-1">
                  <h4 className="font-medium text-lg mb-2">{task.title}</h4>
                  <div className="flex items-center gap-2 mb-2">
                    <Avatar className="h-8 w-8">
                      <AvatarImage src={task.avatar} alt={task.assignee} />
                      <AvatarFallback className="text-sm">
                        {task.assignee.split(" ").map((n) => n[0]).join("")}
                      </AvatarFallback>
                    </Avatar>
                    <span className="text-base text-muted-foreground">{task.assignee}</span>
                  </div>
                  <div className="flex items-center gap-2">
                    <div className={`w-3 h-3 rounded-full ${getPriorityColor(task.priority)}`} />
                    <span className="text-base text-muted-foreground">Due: {task.dueDate}</span>
                  </div>
                </div>
                <div className="text-base px-3 py-1 rounded-full bg-secondary text-secondary-foreground">
                  {task.priority}
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
