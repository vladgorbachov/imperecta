import { Routes, Route, useNavigate } from 'react-router-dom'
import { ThemeProvider } from '@/app/providers/theme-provider'
import { LanguageProvider } from '@/app/providers/language-provider'
import { SupabaseProvider } from '@/shared/contexts/supabase-context'
import { Toaster } from '@/shared/components/ui/sonner'
import { Card, CardContent, CardHeader, CardTitle } from '@/shared/components/ui/card'
import { Button } from '@/shared/components/ui/button'
import DashboardLayout from '@/app/layouts/dashboard-layout'
import LoginPage from '@/features/auth/login-page'
import DashboardPage from '@/app/routes/dashboard-page'
import CalendarPage from '@/app/routes/calendar-page'
import ClientsPage from '@/app/routes/clients-page'
import DocumentsPage from '@/app/routes/documents-page'
import FinancePage from '@/app/routes/finance-page'
import ProjectsPage from '@/features/projects/projects-page'
import TasksPage from '@/features/tasks/tasks-page'
import TeamPage from '@/app/routes/team-page'
import ProfilePage from '@/app/routes/profile-page'
import MarketingPage from '@/app/routes/marketing-page'
import MarketerPage from '@/features/agents/marketer-page'
import ProvidersSettingsPage from '@/features/agents/providers-settings-page'
import AIWorkersHubPage from '@/features/agents/workers-hub-page'
import CustomersPage from '@/app/routes/customers-page'
import SalesPage from '@/app/routes/sales-page'
import OperationsPage from '@/app/routes/operations-page'
import InventoryPage from '@/app/routes/inventory-page'
import Analytics2Page from '@/app/routes/analytics2-page'
import CommunicationsPage from '@/app/routes/communications-page'
import MarketingAnalyticsPage from '@/app/routes/marketing-analytics-page'
import MarketingInsightsPage from '@/app/routes/marketing-insights-page'
import { useLanguage } from '@/app/providers/language-provider'

function AIAssistantPage() {
  const { t } = useLanguage()
  const navigate = useNavigate()
  return (
    <div className="p-4 grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
      <Card>
        <CardHeader>
          <CardTitle>Providers</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={() => navigate('/ai/providers')}>{t('', 'open')} Providers</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Marketer</CardTitle>
        </CardHeader>
        <CardContent>
          <Button onClick={() => navigate('/ai/marketer')}>{t('', 'open')} Marketer</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Sales (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Lawer (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
      <Card>
        <CardHeader>
          <CardTitle>Account Manager (soon)</CardTitle>
        </CardHeader>
        <CardContent>
          <Button variant="secondary" disabled>Coming soon</Button>
        </CardContent>
      </Card>
    </div>
  )
}
function AIInsightsPage() { const { t } = useLanguage(); return <div className="p-4">{t('', 'aiInsights')} (anomalies, recommendations, trends, competitors)</div> }

function App() {
  return (
    <SupabaseProvider>
      <ThemeProvider defaultTheme="system" enableSystem>
        <LanguageProvider>
          <div className="min-h-screen bg-background">
            <Routes>
              <Route path="/login" element={<LoginPage />} />
              <Route path="/" element={<DashboardLayout />}>
                <Route index element={<DashboardPage />} />
                <Route path="dashboard" element={<DashboardPage />} />
                <Route path="customers" element={<CustomersPage />} />
                
                <Route path="finance" element={<FinancePage />} />
                <Route path="projects" element={<ProjectsPage />} />
                <Route path="tasks" element={<TasksPage />} />
                <Route path="team" element={<TeamPage />} />
                <Route path="operations" element={<OperationsPage />} />
                <Route path="inventory" element={<InventoryPage />} />
                <Route path="analytics" element={<Analytics2Page />} />
                <Route path="communications" element={<CommunicationsPage />} />
                <Route path="marketing" element={<MarketingPage />} />
                <Route path="marketing/analytics" element={<MarketingAnalyticsPage />} />
                <Route path="marketing/insights" element={<MarketingInsightsPage />} />
                <Route path="calendar" element={<CalendarPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="ai/assistant" element={<AIAssistantPage />} />
                <Route path="ai/insights" element={<AIInsightsPage />} />
                <Route path="ai/marketer" element={<MarketerPage />} />
                <Route path="ai/providers" element={<ProvidersSettingsPage />} />
                
              </Route>
            </Routes>
            <Toaster />
          </div>
        </LanguageProvider>
      </ThemeProvider>
    </SupabaseProvider>
  )
}

export default App 