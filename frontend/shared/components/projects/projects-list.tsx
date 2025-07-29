import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Badge } from "@/shared/components/ui/badge"
import { Button } from "@/shared/components/ui/button"

interface Project {
  id: string
  name: string
  description: string
  status: 'active' | 'completed' | 'on-hold'
  progress: number
  team: string[]
  dueDate: string
}

const mockProjects: Project[] = [
  {
    id: "1",
    name: "Website Redesign",
    description: "Complete redesign of the company website with modern UI/UX",
    status: "active",
    progress: 75,
    team: ["John Doe", "Jane Smith", "Bob Johnson"],
    dueDate: "2024-03-15",
  },
  {
    id: "2",
    name: "Mobile App Development",
    description: "Development of a new mobile application for iOS and Android",
    status: "active",
    progress: 45,
    team: ["Alice Brown", "Charlie Wilson"],
    dueDate: "2024-05-20",
  },
  {
    id: "3",
    name: "Database Migration",
    description: "Migration from legacy database to new cloud-based solution",
    status: "completed",
    progress: 100,
    team: ["David Lee", "Eva Garcia"],
    dueDate: "2024-02-10",
  },
]

export function ProjectsList() {
  const getStatusColor = (status: Project['status']) => {
    switch (status) {
      case 'active':
        return 'bg-green-100 text-green-800'
      case 'completed':
        return 'bg-blue-100 text-blue-800'
      case 'on-hold':
        return 'bg-yellow-100 text-yellow-800'
      default:
        return 'bg-gray-100 text-gray-800'
    }
  }

  return (
    <div className="page-grid">
      {mockProjects.map((project) => (
        <div key={project.id} className="page-grid-item">
          <Card className="dark:neon-glow h-full">
            <CardHeader>
              <div className="flex items-center justify-between">
                <div>
                  <CardTitle className="text-lg dark:gradient-text">{project.name}</CardTitle>
                  <CardDescription>{project.description}</CardDescription>
                </div>
                <Badge className={getStatusColor(project.status)}>
                  {project.status}
                </Badge>
              </div>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                <div className="flex items-center justify-between text-sm">
                  <span>Progress</span>
                  <span>{project.progress}%</span>
                </div>
                <div className="w-full bg-gray-200 rounded-full h-2">
                  <div
                    className="bg-blue-600 h-2 rounded-full"
                    style={{ width: `${project.progress}%` }}
                  />
                </div>
                <div className="flex items-center justify-between text-sm">
                  <span>Team: {project.team.join(', ')}</span>
                  <span>Due: {new Date(project.dueDate).toLocaleDateString()}</span>
                </div>
                <div className="flex gap-2">
                  <Button size="sm" className="dark:neon-glow">View Details</Button>
                  <Button size="sm" variant="outline" className="dark:neon-glow">Edit</Button>
                </div>
              </div>
            </CardContent>
          </Card>
        </div>
      ))}
    </div>
  )
} 