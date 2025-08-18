import { withPermission } from '@/shared/hocs/with-permission'
import { Card, CardContent } from '@/shared/components/ui/card'
import FloatingCat from '@/shared/components/ui/floating-cat'

function MarketingPage() {
  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">Marketing</h2>
      <Card>
        <CardContent className="pt-6">
          <div className="text-sm text-muted-foreground">Add your marketing dashboards and widgets here.</div>
        </CardContent>
      </Card>
      <FloatingCat />
    </div>
  )
}

export default withPermission('ai:agents:marketer')(MarketingPage)


