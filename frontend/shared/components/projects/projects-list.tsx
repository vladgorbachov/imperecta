import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Badge } from "@/shared/components/ui/badge"
import { Button } from "@/shared/components/ui/button"

export function ProjectsList() {
  return (
    <div className="page-grid">
      {/* Empty projects list - to be populated from API */}
      <div className="page-grid-item col-span-full">
        <Card className="dark:neon-glow h-full">
          <CardHeader>
            <CardTitle className="text-lg dark:gradient-text">Projects</CardTitle>
            <CardDescription>No projects to display</CardDescription>
          </CardHeader>
          <CardContent>
            <Button size="sm" className="dark:neon-glow">Create Project</Button>
          </CardContent>
        </Card>
      </div>
    </div>
  )
} 