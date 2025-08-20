import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Input } from '@/shared/components/ui/input'
import { Button } from '@/shared/components/ui/button'
import { useLanguage } from '@/app/providers/language-provider'

export default function CustomersPage() {
  const { t } = useLanguage()
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'customers')}</h1>
        <div className="flex gap-2">
          <Input placeholder={t('', 'search')} />
          <Button>{t('', 'newCustomer')}</Button>
        </div>
      </div>

      <Tabs defaultValue="list" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="list">{t('', 'customersList')}</TabsTrigger>
          <TabsTrigger value="crm">{t('', 'crmPipeline')}</TabsTrigger>
          <TabsTrigger value="segments">{t('', 'segmentation')}</TabsTrigger>
          <TabsTrigger value="history">{t('', 'history')}</TabsTrigger>
          <TabsTrigger value="loyalty">{t('', 'loyalty')}</TabsTrigger>
        </TabsList>

        <TabsContent value="list">
          <Card>
            <CardHeader><CardTitle>{t('', 'allCustomers')}</CardTitle></CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">{t('', 'allCustomers')}</div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="crm">
          <Card>
            <CardHeader><CardTitle>{t('', 'crmPipeline')}</CardTitle></CardHeader>
            <CardContent>
              <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
                {[t('', 'newCustomer'), t('', 'inProgress'), t('', 'negotiations'), t('', 'won')].map(col => (
                  <Card key={col} className="border-dashed">
                    <CardHeader><CardTitle className="text-base">{col}</CardTitle></CardHeader>
                    <CardContent className="space-y-2">
                      <div className="p-3 rounded-md bg-muted/40">{t('', 'leadDeal')}</div>
                      <div className="p-3 rounded-md bg-muted/40">{t('', 'leadDeal')}</div>
                    </CardContent>
                  </Card>
                ))}
              </div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="segments">
          <Card>
            <CardHeader><CardTitle>{t('', 'segmentation')}</CardTitle></CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">{t('', 'segmentation')}</div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="history">
          <Card>
            <CardHeader><CardTitle>{t('', 'history')}</CardTitle></CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">{t('', 'history')}</div>
            </CardContent>
          </Card>
        </TabsContent>
        <TabsContent value="loyalty">
          <Card>
            <CardHeader><CardTitle>{t('', 'loyalty')}</CardTitle></CardHeader>
            <CardContent>
              <div className="text-sm text-muted-foreground">{t('', 'loyalty')}</div>
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>
    </div>
  )
}


