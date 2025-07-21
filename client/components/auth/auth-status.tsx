'use client'

import { useSession } from 'next-auth/react'
import { getConfiguredProviders } from '@/client/utils/auth-providers'
import { Badge } from '@/client/components/ui/badge'
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/client/components/ui/card'
import { Avatar, AvatarFallback, AvatarImage } from '@/client/components/ui/avatar'

export function AuthStatus() {
  const { data: session, status } = useSession()
  const configuredProviders = getConfiguredProviders()

  if (status === 'loading') {
    return (
      <Card>
        <CardHeader>
          <CardTitle>Authentication Status</CardTitle>
          <CardDescription>Loading...</CardDescription>
        </CardHeader>
      </Card>
    )
  }

  return (
    <div className="space-y-4">
      <Card>
        <CardHeader>
          <CardTitle>Authentication Status</CardTitle>
          <CardDescription>Current session and provider information</CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          <div className="flex items-center space-x-4">
            <Badge variant={status === 'authenticated' ? 'default' : 'secondary'}>
              {status === 'authenticated' ? 'Authenticated' : 'Not Authenticated'}
            </Badge>
          </div>

          {session?.user && (
            <div className="flex items-center space-x-4">
              <Avatar>
                <AvatarImage src={session.user.image || ''} alt={session.user.name || ''} />
                <AvatarFallback>
                  {session.user.name?.charAt(0) || session.user.email?.charAt(0) || 'U'}
                </AvatarFallback>
              </Avatar>
              <div>
                <p className="font-medium">{session.user.name}</p>
                <p className="text-sm text-muted-foreground">{session.user.email}</p>
                {session.user.position && (
                  <p className="text-xs text-muted-foreground">{session.user.position}</p>
                )}
              </div>
            </div>
          )}
        </CardContent>
      </Card>

      <Card>
        <CardHeader>
          <CardTitle>Configured Providers</CardTitle>
          <CardDescription>Available authentication methods</CardDescription>
        </CardHeader>
        <CardContent>
          <div className="flex flex-wrap gap-2">
            <Badge variant="outline">Credentials</Badge>
            {configuredProviders.map((provider) => (
              <Badge key={provider} variant="outline">
                {provider.charAt(0).toUpperCase() + provider.slice(1)}
              </Badge>
            ))}
            {configuredProviders.length === 0 && (
              <p className="text-sm text-muted-foreground">
                Only credentials provider is available. Configure OAuth providers in environment variables.
              </p>
            )}
          </div>
        </CardContent>
      </Card>
    </div>
  )
} 
