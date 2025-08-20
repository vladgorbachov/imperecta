import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useLanguage } from '@/app/providers/language-provider'

export default function MarketingInsightsPage() {
  const { t } = useLanguage()
  const schedule = () => {
    const date = new Date(); date.setDate(date.getDate() + 1)
    addCalendarEvent({ title: t('', 'aiInsights'), date, time: '12:00', type: 'event', color: 'bg-violet-500' })
  }
  return (
    <div className="space-y-6">
      <Card>
        <CardHeader><CardTitle>{t('', 'aiInsights')}</CardTitle></CardHeader>
        <CardContent className="space-y-2">
          <div className="text-sm text-muted-foreground">{t('', 'openInsights')}</div>
          <Button size="sm" onClick={schedule}>{t('', 'schedule')} {t('', 'review')}</Button>
        </CardContent>
      </Card>
    </div>
  )
}


