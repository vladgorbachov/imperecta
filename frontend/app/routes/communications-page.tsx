import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useLanguage } from '@/app/providers/language-provider'

export default function CommunicationsPage() {
  const { t } = useLanguage()
  const schedule = (title: string) => {
    const date = new Date(); date.setDate(date.getDate() + 1)
    addCalendarEvent({ title, date, time: '09:30', type: 'meeting', color: 'bg-cyan-500' })
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'communications')}</h1>
        <Button onClick={() => schedule(t('', 'meetings'))}>{t('', 'schedule')}</Button>
      </div>
      <Tabs defaultValue="email" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="email">{t('', 'emailCampaigns')}</TabsTrigger>
          <TabsTrigger value="chats">{t('', 'chatsMessengers')}</TabsTrigger>
          <TabsTrigger value="meetings">{t('', 'meetingsCalendar')}</TabsTrigger>
          <TabsTrigger value="notifications">{t('', 'notifications')}</TabsTrigger>
          <TabsTrigger value="knowledge">{t('', 'knowledgeBase')}</TabsTrigger>
        </TabsList>
        <TabsContent value="email"><Card><CardHeader><CardTitle>Email</CardTitle></CardHeader><CardContent>{t('', 'lists')}</CardContent></Card></TabsContent>
        <TabsContent value="chats"><Card><CardHeader><CardTitle>{t('', 'chats')}</CardTitle></CardHeader><CardContent>{t('', 'history')}</CardContent></Card></TabsContent>
        <TabsContent value="meetings"><Card><CardHeader><CardTitle>{t('', 'meetings')}</CardTitle></CardHeader><CardContent>{t('', 'integrationWithCalendar')}</CardContent></Card></TabsContent>
        <TabsContent value="notifications"><Card><CardHeader><CardTitle>{t('', 'notifications')}</CardTitle></CardHeader><CardContent>{t('', 'rules')}</CardContent></Card></TabsContent>
        <TabsContent value="knowledge"><Card><CardHeader><CardTitle>{t('', 'knowledgeBase')}</CardTitle></CardHeader><CardContent>{t('', 'documentsLabel')}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  )
}


