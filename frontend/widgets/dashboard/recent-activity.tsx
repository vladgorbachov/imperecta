import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"

export function RecentActivity() {
  // const { t } = useLanguage()

  const activities = [
    {
      id: 1,
      type: "project",
      title: "New project created",
      description: "Project Alpha has been created",
      time: "2 hours ago",
      status: "completed",
    },
    {
      id: 2,
      type: "task",
      title: "Task completed",
      description: "User authentication implemented",
      time: "4 hours ago",
      status: "completed",
    },
    {
      id: 3,
      type: "update",
      title: "System update",
      description: "Database migration completed",
      time: "6 hours ago",
      status: "completed",
    },
    {
      id: 4,
      type: "alert",
      title: "Security alert",
      description: "New login detected",
      time: "1 day ago",
      status: "warning",
    },
  ]

  const getTypeColor = (type: string) => {
    switch (type) {
      case "project":
        return "bg-blue-500"
      case "task":
        return "bg-green-500"
      case "update":
        return "bg-purple-500"
      case "alert":
        return "bg-red-500"
      default:
        return "bg-gray-500"
    }
  }

  const getStatusColor = (status: string) => {
    switch (status) {
      case "completed":
        return "bg-green-100 text-green-800 dark:bg-green-900/30 dark:text-green-400"
      case "warning":
        return "bg-yellow-100 text-yellow-800 dark:bg-yellow-900/30 dark:text-yellow-400"
      default:
        return "bg-gray-100 text-gray-800 dark:bg-gray-900/30 dark:text-gray-400"
    }
  }

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent text-2xl dark:gradient-text">
          Recent Activity
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-y-auto max-h-96 pr-2">
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="glass rounded-xl p-4 hover:scale-105 dark:neon-glow">
              <div className="flex items-start gap-3">
                <div className={`w-3 h-3 rounded-full mt-2 ${getTypeColor(activity.type)}`} />
                <div className="flex-1 min-w-0">
                  <div className="flex items-center gap-2 mb-1">
                    <h4 className="font-medium text-lg">{activity.title}</h4>
                    <div className={`text-base px-3 py-1 rounded-full ${getStatusColor(activity.status)}`}>
                      {activity.status}
                    </div>
                  </div>
                  <p className="text-base text-muted-foreground mb-2">{activity.description}</p>
                  <p className="text-base text-muted-foreground">{activity.time}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
