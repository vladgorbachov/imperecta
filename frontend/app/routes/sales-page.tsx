import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { useLanguage } from '@/app/providers/language-provider'

export default function SalesPage() {
  const { t } = useLanguage()
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'sales')}</h1>
        <Button>{t('', 'newDeal')}</Button>
      </div>

      <Tabs defaultValue="pipeline" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="pipeline">{t('', 'pipeline')}</TabsTrigger>
          <TabsTrigger value="quotes">{t('', 'quotes')}</TabsTrigger>
          <TabsTrigger value="proposals">{t('', 'proposals')}</TabsTrigger>
          <TabsTrigger value="analytics">{t('', 'salesAnalytics')}</TabsTrigger>
          <TabsTrigger value="forecast">{t('', 'forecast')}</TabsTrigger>
        </TabsList>

        <TabsContent value="pipeline">
          <Card><CardHeader><CardTitle>{t('', 'pipeline')}</CardTitle></CardHeader><CardContent>
            <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
              {[t('', 'newDeal'), t('', 'inProgress'), t('', 'negotiations'), t('', 'won')].map(col => (
                <Card key={col} className="border-dashed"><CardHeader><CardTitle className="text-base">{col}</CardTitle></CardHeader><CardContent className="space-y-2">
                  <div className="p-3 rounded-md bg-muted/40">{t('', 'leadDeal')}</div>
                  <div className="p-3 rounded-md bg-muted/40">{t('', 'leadDeal')}</div>
                </CardContent></Card>
              ))}
            </div>
          </CardContent></Card>
        </TabsContent>
        <TabsContent value="quotes"><Card><CardHeader><CardTitle>{t('', 'quotes')}</CardTitle></CardHeader><CardContent>List/Table</CardContent></Card></TabsContent>
        <TabsContent value="proposals"><Card><CardHeader><CardTitle>{t('', 'proposals')}</CardTitle></CardHeader><CardContent>List/Table</CardContent></Card></TabsContent>
        <TabsContent value="analytics"><Card><CardHeader><CardTitle>{t('', 'salesAnalytics')}</CardTitle></CardHeader><CardContent>Charts & Metrics</CardContent></Card></TabsContent>
        <TabsContent value="forecast"><Card><CardHeader><CardTitle>{t('', 'forecast')}</CardTitle></CardHeader><CardContent>Model</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  )
}


