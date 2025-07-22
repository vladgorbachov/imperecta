import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import { Folder, File, Upload } from "lucide-react"

export default function Documents() {
  return (
    <div className="flex flex-col gap-6 p-6">
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">Documents</h1>
        <Button>
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
        
        <TabsContent value="all" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Documents Explorer</CardTitle>
              <div className="flex items-center gap-2">
                <Input placeholder="Search documents..." className="max-w-sm" />
              </div>
            </CardHeader>
            <CardContent>
              <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
                <div className="flex items-center gap-2 p-3 border rounded-lg">
                  <Folder className="h-5 w-5 text-blue-500" />
                  <span>Project Files</span>
                </div>
                <div className="flex items-center gap-2 p-3 border rounded-lg">
                  <File className="h-5 w-5 text-gray-500" />
                  <span>Report.pdf</span>
                </div>
                <div className="flex items-center gap-2 p-3 border rounded-lg">
                  <File className="h-5 w-5 text-gray-500" />
                  <span>Presentation.pptx</span>
                </div>
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="recent" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Recent Documents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-muted-foreground">No recent documents</div>
            </CardContent>
          </Card>
        </TabsContent>
        
        <TabsContent value="shared" className="mt-6">
          <Card>
            <CardHeader>
              <CardTitle>Shared Documents</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="text-muted-foreground">No shared documents</div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}
