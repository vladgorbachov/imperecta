import { Tabs, TabsContent, TabsList, TabsTrigger } from '@/shared/components/ui/tabs'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import { addCalendarEvent } from '@/shared/utils/calendar-bus'
import { useLanguage } from '@/app/providers/language-provider'

export default function InventoryPage() {
  const { t } = useLanguage()
  const schedule = (title: string) => {
    const date = new Date()
    date.setDate(date.getDate() + 3)
    addCalendarEvent({ title, date, time: '15:00', type: 'reminder', color: 'bg-teal-500' })
  }
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <h1 className="text-2xl font-semibold">{t('', 'inventory')}</h1>
        <Button onClick={() => schedule(t('', 'stocks'))}>{t('', 'schedule')}</Button>
      </div>
      <Tabs defaultValue="items" className="space-y-4">
        <TabsList className="grid grid-cols-5 w-full">
          <TabsTrigger value="items">{t('', 'items')}</TabsTrigger>
          <TabsTrigger value="stock">{t('', 'stock')}</TabsTrigger>
          <TabsTrigger value="suppliers">{t('', 'suppliers')}</TabsTrigger>
          <TabsTrigger value="purchase">{t('', 'purchaseOrders')}</TabsTrigger>
          <TabsTrigger value="tracking">{t('', 'tracking')}</TabsTrigger>
        </TabsList>
        <TabsContent value="items"><Card><CardHeader><CardTitle>{t('', 'productsAndServices')}</CardTitle></CardHeader><CardContent>Catalog</CardContent></Card></TabsContent>
        <TabsContent value="stock"><Card><CardHeader><CardTitle>{t('', 'stocks')}</CardTitle></CardHeader><CardContent>Warehouses & Locations</CardContent></Card></TabsContent>
        <TabsContent value="suppliers"><Card><CardHeader><CardTitle>{t('', 'suppliersList')}</CardTitle></CardHeader><CardContent>Suppliers List</CardContent></Card></TabsContent>
        <TabsContent value="purchase"><Card><CardHeader><CardTitle>{t('', 'purchaseOrders')}</CardTitle></CardHeader><CardContent>Orders</CardContent></Card></TabsContent>
        <TabsContent value="tracking"><Card><CardHeader><CardTitle>{t('', 'tracking')}</CardTitle></CardHeader><CardContent>{t('', 'trackingHistory')}</CardContent></Card></TabsContent>
      </Tabs>
    </div>
  )
}


