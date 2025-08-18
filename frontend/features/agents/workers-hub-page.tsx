import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { useNavigate } from 'react-router-dom'
import { withPermission } from '@/shared/hocs/with-permission'

function WorkersHub() {
  const navigate = useNavigate()
  return (
    <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Providers</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={() => navigate('/ai/providers')}>Open Providers Settings</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Marketer</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={() => navigate('/ai/marketer')}>Open Marketer</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Sales (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Lawer (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Account Manager (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
    </div>
  )
}

export default withPermission('ai:workers')(WorkersHub)


