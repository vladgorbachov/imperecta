import { useSupabase } from '@/shared/contexts/supabase-context'

export function usePermissions() {
  const { user } = useSupabase()

  // Determine superuser in a robust but simple way
  const superuserEmailsEnv = (import.meta.env.VITE_SUPERUSER_EMAILS || '').toString().toLowerCase()
  const superuserIdsEnv = (import.meta.env.VITE_SUPERUSER_IDS || '').toString().toLowerCase()

  const userEmail = (user?.email || '').toLowerCase()
  const userId = (user?.id || '').toLowerCase()
  const isSuperuserByEnv =
    (superuserEmailsEnv && superuserEmailsEnv.split(',').map(s => s.trim()).filter(Boolean).includes(userEmail)) ||
    (superuserIdsEnv && superuserIdsEnv.split(',').map(s => s.trim()).filter(Boolean).includes(userId))

  const isSuperuserByMetadata = Boolean((user as any)?.user_metadata?.is_superuser === true || (user as any)?.user_metadata?.role === 'admin')

  const isSuperuser = Boolean(isSuperuserByEnv || isSuperuserByMetadata)

  // Minimal permission model: only superuser has access to AI workers admin
  const userRole = isSuperuser ? 'superuser' : 'user'

  const permissionsByRole: Record<string, string[]> = {
    superuser: [
      'ai:workers',
      'ai:providers',
      'ai:agents:marketer',
      'ai:agents:sales',
      'ai:agents:lawer',
      'ai:agents:accountManager',
    ],
    user: [],
  }

  const userPermissions = permissionsByRole[userRole] || []

  const hasPermission = (permission: string): boolean => userPermissions.includes(permission)
  const hasAnyPermission = (permissionList: string[]): boolean => permissionList.some(hasPermission)
  const hasAllPermissions = (permissionList: string[]): boolean => permissionList.every(hasPermission)

  return {
    hasPermission,
    hasAnyPermission,
    hasAllPermissions,
    userRole,
    userPermissions,
    isSuperuser,
  }
}