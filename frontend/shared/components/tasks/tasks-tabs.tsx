import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Badge } from "@/shared/components/ui/badge"
import { Button } from "@/shared/components/ui/button"

interface Task {
  id: string
  title: string
  description: string
  status: 'todo' | 'in-progress' | 'done'
  priority: 'low' | 'medium' | 'high'
  assignee: string
  dueDate: string
}

const mockTasks: Task[] = [
  {
    id: "1",
    title: "Design Homepage",
    description: "Create wireframes and mockups for the new homepage",
    status: "todo",
    priority: "high",
    assignee: "John Doe",
    dueDate: "2024-03-10",
  },
  {
    id: "2",
    title: "Implement Authentication",
    description: "Set up user authentication system with JWT",
    status: "in-progress",
    priority: "high",
    assignee: "Jane Smith",
    dueDate: "2024-03-15",
  },
  {
    id: "3",
    title: "Write Documentation",
    description: "Create comprehensive API documentation",
    status: "done",
    priority: "medium",
    assignee: "Bob Johnson",
    dueDate: "2024-03-05",
  },
]

export function TasksTabs() {
  const getPriorityColor = (priority: Task['priority']) => {
    switch (priority) {
      case 'high':
        return 'bg-red-100 text-red-800'
      case 'medium':
        return 'bg-yellow-100 text-yellow-800'
      case 'low':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const getStatusColor = (status: Task['status']) => {
    switch (status) {
      case 'todo':
        return 'bg-gray-100 text-gray-800'
      case 'in-progress':
        return 'bg-blue-100 text-blue-800'
      case 'done':
        return 'bg-green-100 text-green-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  const filterTasksByStatus = (status: Task['status']) => {
    return mockTasks.filter(task => task.status === status)
  }

  return (
    <Tabs defaultValue="all" className="w-full">
      <TabsList className="grid w-full grid-cols-4">
        <TabsTrigger value="all">All Tasks</TabsTrigger>
        <TabsTrigger value="todo">To Do</TabsTrigger>
        <TabsTrigger value="in-progress">In Progress</TabsTrigger>
        <TabsTrigger value="done">Done</TabsTrigger>
      </TabsList>
      
      <TabsContent value="all" className="space-y-4">
        {mockTasks.map((task) => (
          <TaskCard key={task.id} task={task} getPriorityColor={getPriorityColor} getStatusColor={getStatusColor} />
        ))}
      </TabsContent>
      
      <TabsContent value="todo" className="space-y-4">
        {filterTasksByStatus('todo').map((task) => (
          <TaskCard key={task.id} task={task} getPriorityColor={getPriorityColor} getStatusColor={getStatusColor} />
        ))}
      </TabsContent>
      
      <TabsContent value="in-progress" className="space-y-4">
        {filterTasksByStatus('in-progress').map((task) => (
          <TaskCard key={task.id} task={task} getPriorityColor={getPriorityColor} getStatusColor={getStatusColor} />
        ))}
      </TabsContent>
      
      <TabsContent value="done" className="space-y-4">
        {filterTasksByStatus('done').map((task) => (
          <TaskCard key={task.id} task={task} getPriorityColor={getPriorityColor} getStatusColor={getStatusColor} />
        ))}
      </TabsContent>
    </Tabs>
  )
}

function TaskCard({ 
  task, 
  getPriorityColor, 
  getStatusColor 
}: { 
  task: Task
  getPriorityColor: (priority: Task['priority']) => string
  getStatusColor: (status: Task['status']) => string
}) {
  return (
    <Card>
      <CardHeader>
        <div className="flex items-center justify-between">
          <CardTitle className="text-lg">{task.title}</CardTitle>
          <div className="flex gap-2">
            <Badge className={getPriorityColor(task.priority)}>
              {task.priority}
            </Badge>
            <Badge className={getStatusColor(task.status)}>
              {task.status}
            </Badge>
          </div>
        </div>
        <CardDescription>{task.description}</CardDescription>
      </CardHeader>
      <CardContent>
        <div className="flex items-center justify-between">
          <div className="text-sm">
            <p>Assignee: {task.assignee}</p>
            <p>Due: {new Date(task.dueDate).toLocaleDateString()}</p>
          </div>
          <div className="flex gap-2">
            <Button size="sm">Edit</Button>
            <Button size="sm" variant="outline">View</Button>
          </div>
        </div>
      </CardContent>
    </Card>
  )
} 