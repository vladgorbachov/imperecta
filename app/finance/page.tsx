import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { FinancialOverview } from "@/client/components/finance/financial-overview"
import { TransactionsList } from "@/client/components/finance/transactions-list"
import { InvoicesList } from "@/client/components/finance/invoices-list"

export default function FinancePage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <FinancialOverview />
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-2">
          <TransactionsList />
          <InvoicesList />
        </div>
      </div>
    </DashboardLayout>
  )
}
