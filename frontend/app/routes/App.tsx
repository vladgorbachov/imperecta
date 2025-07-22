import { Routes, Route } from 'react-router-dom'
import { ThemeProvider } from '@/app/providers/theme-provider'
import { LanguageProvider } from '@/app/providers/language-provider'
import { SupabaseProvider } from '@/shared/contexts/supabase-context'
import { Toaster } from '@/shared/components/ui/sonner'
import DashboardLayout from '@/app/layouts/dashboard-layout'
import LoginPage from '@/features/auth/login-page'
import DashboardPage from '@/app/routes/dashboard-page'
import AnalyticsPage from '@/app/routes/analytics-page'
import CalendarPage from '@/app/routes/calendar-page'
import ClientsPage from '@/app/routes/clients-page'
import DocumentsPage from '@/app/routes/documents-page'
import FinancePage from '@/app/routes/finance-page'
import ProjectsPage from '@/features/projects/projects-page'
import TasksPage from '@/features/tasks/tasks-page'
import TeamPage from '@/app/routes/team-page'
import ProfilePage from '@/app/routes/profile-page'

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
                <Route path="analytics" element={<AnalyticsPage />} />
                <Route path="calendar" element={<CalendarPage />} />
                <Route path="clients" element={<ClientsPage />} />
                <Route path="documents" element={<DocumentsPage />} />
                <Route path="finance" element={<FinancePage />} />
                <Route path="projects" element={<ProjectsPage />} />
                <Route path="tasks" element={<TasksPage />} />
                <Route path="team" element={<TeamPage />} />
                <Route path="profile" element={<ProfilePage />} />
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