"use client"

import type React from "react"

import { useState } from "react"
import { useSession } from "next-auth/react"
import type { User } from "@/server/auth/types"
import { Button } from "@/client/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Input } from "@/client/components/ui/input"
import { Label } from "@/client/components/ui/label"
import { Avatar, AvatarFallback, AvatarImage } from "@/client/components/ui/avatar"
import { useLanguage } from "@/client/i18n/language-context"
import { toast } from "@/client/hooks/use-toast"
import { Toaster } from "@/client/components/ui/toaster"

export function ProfileForm() {
  const { data: session, update } = useSession()
  const currentUser = session?.user as User | undefined
  const { t } = useLanguage()
  const [name, setName] = useState(currentUser?.name || "")
  const [email, setEmail] = useState(currentUser?.email || "")
  const [position, setPosition] = useState(currentUser?.position || "")

  if (!currentUser) return null

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    // В реальном приложении здесь будет вызов API для обновления данных
    // Для демонстрации мы обновляем сессию на клиенте
    await update({ ...session, user: { ...currentUser, name, email, position } })
    toast({
      title: t("profile", "profileUpdated"),
      description: t("profile", "profileUpdatedDesc"),
    })
  }

  return (
    <>
      <Toaster />
      <Card>
        <CardHeader>
          <CardTitle>{t("common", "profile")}</CardTitle>
          <CardDescription>{t("profile", "updateProfileInfo")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-6">
            <div className="flex items-center gap-4">
              <Avatar className="h-20 w-20">
                <AvatarImage src={currentUser.avatar || "/placeholder.svg"} alt={currentUser.name} />
                <AvatarFallback>
                  {currentUser.name
                    .split(" ")
                    .map((n) => n[0])
                    .join("")}
                </AvatarFallback>
              </Avatar>
              <Button type="button" variant="outline">
                {t("profile", "changeAvatar")}
              </Button>
            </div>
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <Label htmlFor="name">{t("team", "name")}</Label>
                <Input id="name" value={name} onChange={(e) => setName(e.target.value)} />
              </div>
              <div className="space-y-2">
                <Label htmlFor="email">{t("clients", "email")}</Label>
                <Input id="email" type="email" value={email} onChange={(e) => setEmail(e.target.value)} />
              </div>
            </div>
            <div className="space-y-2">
              <Label htmlFor="position">{t("team", "position")}</Label>
              <Input id="position" value={position} onChange={(e) => setPosition(e.target.value)} />
            </div>
            <div className="flex justify-end">
              <Button type="submit">{t("profile", "saveChanges")}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
