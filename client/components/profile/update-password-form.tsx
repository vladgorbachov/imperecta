"use client"

import type React from "react"

import { useState } from "react"
import { Button } from "@/client/components/ui/button"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Input } from "@/client/components/ui/input"
import { Label } from "@/client/components/ui/label"
import { useLanguage } from "@/client/i18n/language-context"
import { toast } from "@/client/hooks/use-toast"
import { Toaster } from "@/client/components/ui/toaster"

export function UpdatePasswordForm() {
  const { t } = useLanguage()
  const [currentPassword, setCurrentPassword] = useState("")
  const [newPassword, setNewPassword] = useState("")
  const [confirmPassword, setConfirmPassword] = useState("")
  const [error, setError] = useState("")

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault()
    setError("")

    if (newPassword !== confirmPassword) {
      setError(t("profile", "passwordsDoNotMatch"))
      return
    }

    // В реальном приложении здесь будет вызов API для смены пароля
    console.log("Password change attempt:", { currentPassword, newPassword })

    toast({
      title: "Функционал в разработке",
      description: "Смена пароля будет реализована через API.",
    })
  }

  return (
    <>
      <Toaster />
      <Card>
        <CardHeader>
          <CardTitle>{t("profile", "changePassword")}</CardTitle>
          <CardDescription>{t("profile", "updatePasswordDesc")}</CardDescription>
        </CardHeader>
        <CardContent>
          <form onSubmit={handleSubmit} className="space-y-4">
            <div className="space-y-2">
              <Label htmlFor="current-password">{t("profile", "currentPassword")}</Label>
              <Input
                id="current-password"
                type="password"
                value={currentPassword}
                onChange={(e) => setCurrentPassword(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="new-password">{t("profile", "newPassword")}</Label>
              <Input
                id="new-password"
                type="password"
                value={newPassword}
                onChange={(e) => setNewPassword(e.target.value)}
              />
            </div>
            <div className="space-y-2">
              <Label htmlFor="confirm-password">{t("profile", "confirmNewPassword")}</Label>
              <Input
                id="confirm-password"
                type="password"
                value={confirmPassword}
                onChange={(e) => setConfirmPassword(e.target.value)}
              />
            </div>
            {error && <p className="text-sm text-destructive">{error}</p>}
            <div className="flex justify-end">
              <Button type="submit">{t("profile", "updatePassword")}</Button>
            </div>
          </form>
        </CardContent>
      </Card>
    </>
  )
}
