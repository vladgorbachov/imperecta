"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/client/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Input } from "@/client/components/ui/input"
import { Label } from "@/client/components/ui/label"
import { Logo } from "@/client/components/ui/logo"
import { useLanguage } from "@/client/i18n/language-context"
import { testUsers } from "@/server/auth/users"
import type { User } from "@/server/auth/types"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { useAuth } from "@/client/hooks/use-auth"
import { getConfiguredProviders } from "@/client/utils/auth-providers"

export default function LoginPage() {
  const [email, setEmail] = useState("")
  const [password, setPassword] = useState("")
  const [error, setError] = useState("")
  const [isDropdownOpen, setIsDropdownOpen] = useState(false)
  const { t } = useLanguage()
  const { login, loginWithProvider, isLoading } = useAuth()
  const configuredProviders = getConfiguredProviders()

  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    try {
      await login(email, password)
    } catch {
      setError(t("profile", "invalidCredentials"))
    }
  }

  const handleUserSelect = (user: User) => {
    setEmail(user.email)
    setPassword(user.password || "")
    setIsDropdownOpen(false)
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-4">
      <Card className="w-full max-w-sm">
        <CardHeader className="text-center">
          <div className="mx-auto mb-4">
            <Logo />
          </div>
          <CardTitle>{t("common", "welcome")}</CardTitle>
          <CardDescription>{t("profile", "loginToAccount")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleLogin} className="space-y-4">
            <div className="space-y-2 relative">
              <Label htmlFor="email">{t("clients", "email")}</Label>
              <Input
                id="email"
                type="email"
                placeholder="m@example.com"
                required
                value={email}
                onChange={(e) => setEmail(e.target.value)}
                onFocus={() => setIsDropdownOpen(true)}
                onBlur={() => setTimeout(() => setIsDropdownOpen(false), 150)}
                autoComplete="off"
              />
              {isDropdownOpen && (
                <div className="absolute z-10 mt-1 w-full rounded-md border bg-card shadow-lg">
                  <ul className="py-1">
                    {testUsers.map((user) => (
                      <li
                        key={user.id}
                        className="flex items-center gap-3 px-4 py-2 text-sm hover:bg-muted cursor-pointer"
                        onMouseDown={(e) => {
                          e.preventDefault()
                          handleUserSelect(user)
                        }}
                      >
                        <Avatar className="h-8 w-8">
                          <AvatarImage src={user.avatar || "/placeholder.svg"} alt={user.name} />
                          <AvatarFallback>
                            {user.name
                              .split(" ")
                              .map((n) => n[0])
                              .join("")}
                          </AvatarFallback>
                        </Avatar>
                        <div>
                          <p className="font-medium">{user.name}</p>
                          <p className="text-xs text-muted-foreground">{user.email}</p>
                        </div>
                      </li>
                    ))}
                  </ul>
                </div>
              )}
            </div>
            <div className="space-y-2">
              <Label htmlFor="password">{t("profile", "password")}</Label>
              <Input
                id="password"
                type="password"
                required
                value={password}
                onChange={(e) => setPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <Button type="submit" className="w-full" disabled={isLoading}>
              {isLoading ? t("profile", "loggingIn") : t("profile", "login")}
            </Button>
          </form>

          {/* OAuth Providers */}
          {configuredProviders.length > 0 && (
            <>
              <div className="relative my-4">
                <div className="absolute inset-0 flex items-center">
                  <span className="w-full border-t" />
                </div>
                <div className="relative flex justify-center text-xs uppercase">
                  <span className="bg-background px-2 text-muted-foreground">
                    Or continue with
                  </span>
                </div>
              </div>

              <div className="space-y-2">
                {configuredProviders.includes('google') && (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => loginWithProvider('google')}
                    disabled={isLoading}
                  >
                    Continue with Google
                  </Button>
                )}
                {configuredProviders.includes('github') && (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => loginWithProvider('github')}
                    disabled={isLoading}
                  >
                    Continue with GitHub
                  </Button>
                )}
                {configuredProviders.includes('email') && (
                  <Button
                    variant="outline"
                    className="w-full"
                    onClick={() => loginWithProvider('email')}
                    disabled={isLoading}
                  >
                    Continue with Email
                  </Button>
                )}
              </div>
            </>
          )}
        </CardContent>
      </Card>
    </div>
  )
}
