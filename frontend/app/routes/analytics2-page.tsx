import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useLanguage } from '@/app/providers/language-provider'

export default function Analytics2Page() {
  const { t } = useLanguage()
  const schedule = (title: string) => {
    const date = new Date(); date.setDate(date.getDate() + 4)
    addCalendarEvent({ title, date, time: '16:00', type: 'event', color: 'bg-indigo-500' })
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'analytics')}</h1>
        <Button onClick={() => schedule(t('', 'weeklyReport'))}>{t('', 'schedule')}</Button>
      </div>
      <Tabs defaultValue="dashboards" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="dashboards">{t('', 'analytics')}</TabsTrigger>
          <TabsTrigger value="reports">{t('', 'reports') || 'Reports'}</TabsTrigger>
          <TabsTrigger value="kpi">KPI</TabsTrigger>
          <TabsTrigger value="forecast">{t('', 'forecast')}</TabsTrigger>
          <TabsTrigger value="compare">{t('', 'compare') || 'Compare'}</TabsTrigger>
        </TabsList>
        <TabsContent value="dashboards"><Card><CardHeader><CardTitle>{t('', 'analytics')}</CardTitle></CardHeader><CardContent>Charts</CardContent></Card></TabsContent>
        <TabsContent value="reports"><Card><CardHeader><CardTitle>{t('', 'reports') || 'Reports'}</CardTitle></CardHeader><CardContent>Builder</CardContent></Card></TabsContent>
        <TabsContent value="kpi"><Card><CardHeader><CardTitle>KPI</CardTitle></CardHeader><CardContent>KPI Cards</CardContent></Card></TabsContent>
        <TabsContent value="forecast"><Card><CardHeader><CardTitle>{t('', 'forecast')}</CardTitle></CardHeader><CardContent>Models</CardContent></Card></TabsContent>
        <TabsContent value="compare"><Card><CardHeader><CardTitle>{t('', 'compare') || 'Compare'}</CardTitle></CardHeader><CardContent>Table</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  )
}


