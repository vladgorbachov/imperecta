import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import { Folder, File, Upload } from "lucide-react"

export default function Documents() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold dark:gradient-text">Documents</h1>
        <Button className="dark:neon-glow">
          <Upload className="mr-2 h-4 w-4" />
          Upload
        </Button>
      </div>
      
      <Tabs defaultValue="all" className="w-full">
        <TabsList>
          <TabsTrigger value="all">All Documents</TabsTrigger>
          <TabsTrigger value="recent">Recent</TabsTrigger>
          <TabsTrigger value="shared">Shared</TabsTrigger>
        </TabsList>
        
        <TabsContent value="all" className="page-grid">
          <div className="page-grid-item col-span-full">
            <Card className="dark:neon-glow h-full">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Documents Explorer</CardTitle>
                <div className="flex items-center gap-2">
                  <Input placeholder="Search documents..." className="max-w-sm dark:neon-glow" />
                </div>
              </CardHeader>
              <CardContent>
                <div className="page-grid">
                  <div className="page-grid-item">
                    <div className="flex items-center gap-2 p-3 border rounded-lg dark:neon-glow">
                      <Folder className="h-5 w-5 text-blue-500" />
                      <span>Project Files</span>
                    </div>
                  </div>
                  <div className="page-grid-item">
                    <div className="flex items-center gap-2 p-3 border rounded-lg dark:neon-glow">
                      <File className="h-5 w-5 text-gray-500" />
                      <span>Report.pdf</span>
                    </div>
                  </div>
                  <div className="page-grid-item">
                    <div className="flex items-center gap-2 p-3 border rounded-lg dark:neon-glow">
                      <File className="h-5 w-5 text-gray-500" />
                      <span>Presentation.pptx</span>
                    </div>
                  </div>
                </div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        <TabsContent value="recent" className="page-grid">
          <div className="page-grid-item col-span-full">
            <Card className="dark:neon-glow h-full">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Recent Documents</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-muted-foreground">No recent documents</div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
        
        <TabsContent value="shared" className="page-grid">
          <div className="page-grid-item col-span-full">
            <Card className="dark:neon-glow h-full">
              <CardHeader>
                <CardTitle className="dark:gradient-text">Shared Documents</CardTitle>
              </CardHeader>
              <CardContent>
                <div className="text-muted-foreground">No shared documents</div>
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>
    </div>
  )
}
