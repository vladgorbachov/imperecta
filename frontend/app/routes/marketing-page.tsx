import { withPermission } from '@/shared/hocs/with-permission'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import FloatingCat from '@/shared/components/ui/floating-cat'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useNavigate } from 'react-router-dom'
import { useLanguage } from '@/app/providers/language-provider'

function MarketingPage() {
  const navigate = useNavigate()
  const { t } = useLanguage()
  const schedule = (title: string) => {
    const date = new Date()
    date.setDate(date.getDate() + 1)
    addCalendarEvent({ title, date, time: '11:00', type: 'event', color: 'bg-pink-500' })
  }

  return (
    <div className="space-y-6">
      <h2 className="text-xl font-semibold">{t('', 'marketing')}</h2>

      <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
        <Card>
          <CardHeader><CardTitle>{t('', 'contentPlan')}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm text-muted-foreground">{t('', 'contentPlan')}</div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => schedule(t('', 'editorialMeeting'))}>{t('', 'schedule')}</Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t('', 'campaigns')}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm text-muted-foreground">{t('', 'campaigns')}</div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => schedule(t('', 'launchCampaign'))}>{t('', 'schedule')}</Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t('', 'analytics')}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm text-muted-foreground">{t('', 'analytics')}</div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => navigate('/marketing/analytics')}>{t('', 'openAnalytics')}</Button>
              <Button size="sm" variant="secondary" onClick={() => schedule(t('', 'weeklyReport'))}>{t('', 'schedule')}</Button>
            </div>
          </CardContent>
        </Card>
        <Card>
          <CardHeader><CardTitle>{t('', 'aiInsights')}</CardTitle></CardHeader>
          <CardContent className="space-y-2">
            <div className="text-sm text-muted-foreground">{t('', 'aiInsights')}</div>
            <div className="flex gap-2">
              <Button size="sm" onClick={() => navigate('/marketing/insights')}>{t('', 'openInsights')}</Button>
            </div>
          </CardContent>
        </Card>
      </div>

      <FloatingCat />
    </div>
  )
}

export default withPermission('ai:agents:marketer')(MarketingPage)


