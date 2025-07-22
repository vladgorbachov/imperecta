import { createContext, useContext, useState, ReactNode } from 'react'

export interface Organization {
  id: string
  name: string
  slug: string
  plan: 'free' | 'pro' | 'enterprise'
  settings: {
    theme: 'light' | 'dark' | 'system'
    language: string
    timezone: string
  }
}

interface OrganizationContextType {
  currentOrg: Organization | null
  switchOrg: (orgId: string) => void
  organizations: Organization[]
  isLoading: boolean
}

const OrganizationContext = createContext<OrganizationContextType | undefined>(undefined)

interface OrganizationProviderProps {
  children: ReactNode
}

export function OrganizationProvider({ children }: OrganizationProviderProps) {
  const [currentOrg, setCurrentOrg] = useState<Organization | null>(null)
  const [isLoading, setIsLoading] = useState(false)

  // Mock organizations - in real app this would come from API
  const organizations: Organization[] = [
    {
      id: '1',
      name: 'Acme Corp',
      slug: 'acme-corp',
      plan: 'enterprise',
      settings: {
        theme: 'system',
        language: 'en',
        timezone: 'UTC',
      },
    },
    {
      id: '2',
      name: 'Startup Inc',
      slug: 'startup-inc',
      plan: 'pro',
      settings: {
        theme: 'light',
        language: 'en',
        timezone: 'UTC',
      },
    },
  ]

  const switchOrg = async (orgId: string) => {
    setIsLoading(true)
    try {
      // In real app, this would make an API call to switch organizations
      const org = organizations.find(o => o.id === orgId)
      if (org) {
        setCurrentOrg(org)
        // Update user preferences, theme, etc.
      }
    } catch (error) {
      console.error('Failed to switch organization:', error)
    } finally {
      setIsLoading(false)
    }
  }

  return (
    <OrganizationContext.Provider
      value={{
        currentOrg,
        switchOrg,
        organizations,
        isLoading,
      }}
    >
      {children}
    </OrganizationContext.Provider>
  )
}

export function useOrganization() {
  const context = useContext(OrganizationContext)
  if (context === undefined) {
    throw new Error('useOrganization must be used within an OrganizationProvider')
  }
  return context
} 