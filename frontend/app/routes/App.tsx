import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/app/providers/theme-provider'
import { LanguageProvider } from '@/app/providers/language-provider'
import { SupabaseProvider } from '@/shared/contexts/supabase-context'
import { Toaster } from '@/shared/components/ui/sonner'
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
                <Route path="marketing" element={<MarketingPage />} />
                <Route path="calendar" element={<CalendarPage />} />
                <Route path="clients" element={<ClientsPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="finance" element={<FinancePage />} />
                <Route path="projects" element={<ProjectsPage />} />
                <Route path="tasks" element={<TasksPage />} />
                <Route path="profile" element={<ProfilePage />} />
                <Route path="ai/marketer" element={<MarketerPage />} />
                <Route path="ai/providers" element={<ProvidersSettingsPage />} />
                <Route path="ai/workers" element={<AIWorkersHubPage />} />
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