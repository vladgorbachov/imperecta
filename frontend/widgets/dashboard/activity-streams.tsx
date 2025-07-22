import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Avatar, AvatarFallback, AvatarImage } from "@/shared/components/ui/avatar"

export function ActivityStreams() {
  // const { t } = useLanguage()

  const activities = [
    {
      id: 1,
      user: "John Doe",
      avatar: "/placeholder-user.jpg",
      action: "commented on",
      target: "Project Alpha",
      time: "2 minutes ago",
    },
    {
      id: 2,
      user: "Jane Smith",
      avatar: "/placeholder-user.jpg",
      action: "updated",
      target: "Task #123",
      time: "5 minutes ago",
    },
    {
      id: 3,
      user: "Bob Johnson",
      avatar: "/placeholder-user.jpg",
      action: "created",
      target: "New Project",
      time: "10 minutes ago",
    },
    {
      id: 4,
      user: "Alice Brown",
      avatar: "/placeholder-user.jpg",
      action: "completed",
      target: "Task #456",
      time: "15 minutes ago",
    },
  ]

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="bg-gradient-to-r from-blue-600 to-purple-600 bg-clip-text text-transparent text-2xl">
          Activity Streams
        </CardTitle>
      </CardHeader>
      <CardContent className="overflow-y-auto max-h-96 pr-2">
        <div className="space-y-4">
          {activities.map((activity) => (
            <div key={activity.id} className="glass rounded-xl p-4 hover:scale-105">
              <div className="flex items-start gap-3">
                <Avatar className="h-10 w-10">
                  <AvatarImage src={activity.avatar} alt={activity.user} />
                  <AvatarFallback className="text-sm">
                    {activity.user.split(" ").map((n) => n[0]).join("")}
                  </AvatarFallback>
                </Avatar>
                <div className="flex-1 min-w-0">
                  <p className="text-base">
                    <span className="font-medium">{activity.user}</span>{" "}
                    <span className="text-muted-foreground">{activity.action}</span>{" "}
                    <span className="font-medium">{activity.target}</span>
                  </p>
                  <p className="text-base text-muted-foreground mt-1">{activity.time}</p>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
