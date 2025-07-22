import { ComponentType } from 'react'
import { usePermissions } from '@/shared/hooks/use-permissions'

// interface PermissionProps {
//   permission: string
// }

export const withPermission = (permission: string) => {
  return <P extends object>(Component: ComponentType<P>) => {
    const WithPermissionComponent = (props: P) => {
      const { hasPermission } = usePermissions()
      
      if (!hasPermission(permission)) {
        return <AccessDenied />
      }
      
      return <Component {...props} />
    }
    
    WithPermissionComponent.displayName = `withPermission(${Component.displayName || Component.name})`
    
    return WithPermissionComponent
  }
}

// Access Denied component
function AccessDenied() {
  return (
    <div className="flex items-center justify-center min-h-[200px]">
      <div className="text-center">
        <h3 className="text-lg font-semibold text-destructive mb-2">Access Denied</h3>
        <p className="text-muted-foreground">
          You don't have permission to access this resource.
        </p>
      </div>
    </div>
  )
} 