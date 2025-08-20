import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useLanguage } from '@/app/providers/language-provider'

export default function OperationsPage() {
  const { t } = useLanguage()
  const schedule = (title: string) => {
    const date = new Date()
    date.setDate(date.getDate() + 2)
    addCalendarEvent({ title, date, time: '10:00', type: 'meeting', color: 'bg-amber-500' })
  }

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'operations')}</h1>
        <Button onClick={() => schedule(t('', 'businessProcesses'))}>{t('', 'schedule')}</Button>
      </div>

      <Tabs defaultValue="processes" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="processes">{t('', 'processes')}</TabsTrigger>
          <TabsTrigger value="automation">{t('', 'automation')}</TabsTrigger>
          <TabsTrigger value="workflows">{t('', 'workflows')}</TabsTrigger>
          <TabsTrigger value="sop">{t('', 'sop')}</TabsTrigger>
          <TabsTrigger value="quality">{t('', 'quality')}</TabsTrigger>
        </TabsList>

        <TabsContent value="processes">
          <Card>
            <CardHeader><CardTitle>{t('', 'businessProcesses')}</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
                {[t('', 'drafts'), t('', 'active'), t('', 'onReview')].map((col) => (
                  <Card key={col} className="border-dashed">
                    <CardHeader><CardTitle className="text-base">{col}</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      <div className="p-3 rounded-md bg-muted/40">{t('', 'processes')}</div>
                      <div className="p-3 rounded-md bg-muted/40">{t('', 'processes')}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="automation">
          <Card><CardHeader><CardTitle>{t('', 'automation')}</CardTitle></CardHeader><CardContent>Rules & Triggers</CardContent></Card>
        </TabsContent>
        <TabsContent value="workflows">
          <Card><CardHeader><CardTitle>{t('', 'workflows')}</CardTitle></CardHeader><CardContent>Workflow Builder</CardContent></Card>
        </TabsContent>
        <TabsContent value="sop">
          <Card><CardHeader><CardTitle>SOP</CardTitle></CardHeader><CardContent>Procedures & Versions</CardContent></Card>
        </TabsContent>
        <TabsContent value="quality">
          <Card><CardHeader><CardTitle>{t('', 'quality')}</CardTitle></CardHeader><CardContent>Checklists, SLA, Metrics</CardContent></Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}


