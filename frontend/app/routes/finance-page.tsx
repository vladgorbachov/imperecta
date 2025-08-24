import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/shared/components/ui/tabs"
import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Button } from "@/shared/components/ui/button"
import { Input } from "@/shared/components/ui/input"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table"
import { addCalendarEvent } from "@/shared/utils/calendar-bus"
import { useLanguage } from "@/app/providers/language-provider"

export default function Finance() {
  const { t } = useLanguage()
  const schedule = (title: string, dateStr?: string) => {
    const date = dateStr ? new Date(dateStr) : new Date()
    if (!dateStr) date.setDate(date.getDate() + 1)
    addCalendarEvent({ title, date, time: '10:00', type: 'reminder', color: 'bg-rose-500' })
  }

  return (
    <Tabs defaultValue="invoices" className="space-y-4">
      <TabsList className="grid grid-cols-4 w-full text-sm h-9">
        <TabsTrigger value="invoices">{t('', 'invoices')}</TabsTrigger>
        <TabsTrigger value="budgets">{t('', 'budgets')}</TabsTrigger>
        <TabsTrigger value="transactions">{t('', 'transactions')}</TabsTrigger>
        <TabsTrigger value="sales">{t('', 'sales') || 'Sales'}</TabsTrigger>
      </TabsList>

      <TabsContent value="invoices">
        <Card className="dark:neon-glow">
          <CardHeader className="flex items-center justify-between py-3">
            <CardTitle className="text-base dark:gradient-text">{t('', 'invoices')}</CardTitle>
            <div className="flex items-center gap-2">
              <Input type="search" placeholder={t('', 'search')} className="search-input h-10 w-48 text-sm" />
              <Button size="sm" onClick={() => schedule(t('', 'invoices'))}>{t('', 'schedule')}</Button>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('', 'number')}</TableHead>
                  <TableHead>{t('', 'client')}</TableHead>
                  <TableHead>{t('', 'status')}</TableHead>
                  <TableHead>{t('', 'issuedOn')}</TableHead>
                  <TableHead>{t('', 'dueDate')}</TableHead>
                  <TableHead className="text-right">{t('', 'amount')}</TableHead>
                  <TableHead className="text-right">{t('', 'balance')}</TableHead>
                  <TableHead></TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Empty state */}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="budgets">
        <Card className="dark:neon-glow">
          <CardHeader className="flex items-center justify-between py-3">
            <CardTitle className="text-base dark:gradient-text">{t('', 'budgets')}</CardTitle>
            <div className="flex items-center gap-2">
              <Input type="search" placeholder={t('', 'search')} className="search-input h-10 w-48 text-sm" />
              <Button size="sm" onClick={() => schedule(t('', 'review'))}>{t('', 'schedule')}</Button>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('', 'name')}</TableHead>
                  <TableHead>{t('', 'period')}</TableHead>
                  <TableHead>{t('', 'dates')}</TableHead>
                  <TableHead>{t('', 'status')}</TableHead>
                  <TableHead className="text-right">{t('', 'total')}</TableHead>
                  <TableHead className="text-right">{t('', 'allocated')}</TableHead>
                  <TableHead className="text-right">{t('', 'spent')}</TableHead>
                  <TableHead className="text-right">{t('', 'remaining')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Empty state */}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="transactions">
        <Card className="dark:neon-glow">
          <CardHeader className="flex items-center justify-between py-3">
            <CardTitle className="text-base dark:gradient-text">{t('', 'transactions')}</CardTitle>
            <div className="flex items-center gap-2">
              <Input type="search" placeholder={t('', 'filter')} className="search-input h-10 w-48 text-sm" />
              <Button size="sm" onClick={() => schedule(t('', 'transactions'))}>{t('', 'schedule')}</Button>
            </div>
          </CardHeader>
          <CardContent className="py-2">
            <Table>
              <TableHeader>
                <TableRow>
                  <TableHead>{t('', 'date')}</TableHead>
                  <TableHead>{t('', 'type')}</TableHead>
                  <TableHead>{t('', 'status')}</TableHead>
                  <TableHead className="text-right">{t('', 'amount')}</TableHead>
                  <TableHead>{t('', 'currency')}</TableHead>
                  <TableHead>{t('', 'from')}</TableHead>
                  <TableHead>{t('', 'to')}</TableHead>
                  <TableHead>{t('', 'reference')}</TableHead>
                </TableRow>
              </TableHeader>
              <TableBody>
                {/* Empty state */}
              </TableBody>
            </Table>
          </CardContent>
        </Card>
      </TabsContent>

      <TabsContent value="sales">
        <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
          <Card className="dark:neon-glow">
            <CardHeader className="py-3"><CardTitle className="text-base">{t('', 'pipeline')}</CardTitle></CardHeader>
            <CardContent className="py-2 text-sm text-muted-foreground">{/* Empty state */}</CardContent>
          </Card>
          <Card className="dark:neon-glow">
            <CardHeader className="py-3"><CardTitle className="text-base">{t('', 'quotes')}</CardTitle></CardHeader>
            <CardContent className="py-2 text-sm text-muted-foreground">{/* Empty state */}</CardContent>
          </Card>
          <Card className="dark:neon-glow">
            <CardHeader className="py-3"><CardTitle className="text-base">{t('', 'proposals')}</CardTitle></CardHeader>
            <CardContent className="py-2 text-sm text-muted-foreground">{/* Empty state */}</CardContent>
          </Card>
          <Card className="dark:neon-glow">
            <CardHeader className="py-3"><CardTitle className="text-base">{t('', 'salesAnalytics')}</CardTitle></CardHeader>
            <CardContent className="py-2 text-sm text-muted-foreground">{/* Empty state */}</CardContent>
          </Card>
        </div>
      </TabsContent>
    </Tabs>
  )
}
