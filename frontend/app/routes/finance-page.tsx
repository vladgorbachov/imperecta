import { Card, CardContent, CardHeader, CardTitle } from "@/shared/components/ui/card"
import { Table, TableBody, TableCell, TableHead, TableHeader, TableRow } from "@/shared/components/ui/table"
import { DollarSign, TrendingUp, TrendingDown, CreditCard } from "lucide-react"

export default function Finance() {
  return (
    <div className="space-y-6">
      <div className="page-grid">
        <div className="page-grid-item">
          <Card className="dark:neon-glow h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium dark:gradient-text">Total Revenue</CardTitle>
              <DollarSign className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold dark:text-glow">$45,231.89</div>
              <p className="text-xs text-muted-foreground">+20.1% from last month</p>
            </CardContent>
          </Card>
        </div>
        
        <div className="page-grid-item">
          <Card className="dark:neon-glow h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium dark:gradient-text">Total Expenses</CardTitle>
              <TrendingDown className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold dark:text-glow">$12,234.56</div>
              <p className="text-xs text-muted-foreground">+5.2% from last month</p>
            </CardContent>
          </Card>
        </div>
        
        <div className="page-grid-item">
          <Card className="dark:neon-glow h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium dark:gradient-text">Net Profit</CardTitle>
              <TrendingUp className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold dark:text-glow">$32,997.33</div>
              <p className="text-xs text-muted-foreground">+15.3% from last month</p>
            </CardContent>
          </Card>
        </div>
        
        <div className="page-grid-item">
          <Card className="dark:neon-glow h-full">
            <CardHeader className="flex flex-row items-center justify-between space-y-0 pb-2">
              <CardTitle className="text-sm font-medium dark:gradient-text">Pending Invoices</CardTitle>
              <CreditCard className="h-4 w-4 text-muted-foreground" />
            </CardHeader>
            <CardContent>
              <div className="text-2xl font-bold dark:text-glow">12</div>
              <p className="text-xs text-muted-foreground">$8,234.00 total</p>
            </CardContent>
          </Card>
        </div>
      </div>
      
      <div className="page-grid">
        <div className="page-grid-item col-span-full">
          <Card className="dark:neon-glow h-full">
            <CardHeader>
              <CardTitle className="dark:gradient-text">Recent Invoices</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Invoice</TableHead>
                    <TableHead>Client</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Status</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>INV-001</TableCell>
                    <TableCell>Acme Corp</TableCell>
                    <TableCell>$1,200.00</TableCell>
                    <TableCell><div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-primary text-primary-foreground">Paid</div></TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>INV-002</TableCell>
                    <TableCell>Tech Solutions</TableCell>
                    <TableCell>$2,500.00</TableCell>
                    <TableCell><div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-secondary text-secondary-foreground">Pending</div></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
      
      <div className="page-grid">
        <div className="page-grid-item col-span-full">
          <Card className="dark:neon-glow h-full">
            <CardHeader>
              <CardTitle className="dark:gradient-text">Recent Transactions</CardTitle>
            </CardHeader>
            <CardContent>
              <Table>
                <TableHeader>
                  <TableRow>
                    <TableHead>Date</TableHead>
                    <TableHead>Description</TableHead>
                    <TableHead>Amount</TableHead>
                    <TableHead>Type</TableHead>
                  </TableRow>
                </TableHeader>
                <TableBody>
                  <TableRow>
                    <TableCell>2024-01-15</TableCell>
                    <TableCell>Office Supplies</TableCell>
                    <TableCell>-$150.00</TableCell>
                    <TableCell><div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-destructive text-destructive-foreground">Expense</div></TableCell>
                  </TableRow>
                  <TableRow>
                    <TableCell>2024-01-14</TableCell>
                    <TableCell>Client Payment</TableCell>
                    <TableCell>+$1,200.00</TableCell>
                    <TableCell><div className="inline-flex items-center rounded-full border px-2.5 py-0.5 text-xs font-semibold bg-primary text-primary-foreground">Income</div></TableCell>
                  </TableRow>
                </TableBody>
              </Table>
            </CardContent>
          </Card>
        </div>
      </div>
    </div>
  )
}
