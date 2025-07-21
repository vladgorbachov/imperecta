import { DashboardLayout } from "@/client/components/layouts/dashboard-layout"
import { ProfileForm } from "@/client/components/profile/profile-form"
import { UpdatePasswordForm } from "@/client/components/profile/update-password-form"
import { AuthStatus } from "@/client/components/auth/auth-status"

export default function ProfilePage() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6 p-6">
        <div className="grid grid-cols-1 gap-6 lg:grid-cols-3">
          <div className="lg:col-span-2">
            <ProfileForm />
          </div>
          <div className="space-y-6">
            <UpdatePasswordForm />
            <AuthStatus />
          </div>
        </div>
      </div>
    </DashboardLayout>
  )
}
