"use client"

import { Plus, FileText, Users, Calendar, MessageSquare, Zap } from "lucide-react"
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/client/components/ui/card"
import { Button } from "@/client/components/ui/button"
import { useLanguage } from "@/client/i18n/language-context"

export function QuickActions() {
  const { t } = useLanguage()

  const actions = [
    {
      icon: Plus,
      label: t("common", "newProject"),
      variant: "default" as const,
      gradient: "from-blue-500 to-purple-600",
    },
    {
      icon: FileText,
      label: t("dashboard", "createReport"),
      variant: "outline" as const,
      gradient: "from-green-500 to-blue-600",
    },
    {
      icon: Users,
      label: t("dashboard", "manageTeam"),
      variant: "outline" as const,
      gradient: "from-purple-500 to-pink-600",
    },
    {
      icon: Calendar,
      label: t("dashboard", "scheduleMeeting"),
      variant: "outline" as const,
      gradient: "from-orange-500 to-red-600",
    },
    {
      icon: MessageSquare,
      label: t("dashboard", "sendMessage"),
      variant: "outline" as const,
      gradient: "from-cyan-500 to-blue-600",
    },
  ]

  return (
    <Card className="glass-card h-full">
      <CardHeader className="pb-4">
        <CardTitle className="text-xl font-bold bg-gradient-to-r from-orange-600 to-red-600 bg-clip-text text-transparent">
          {t("dashboard", "quickActions")}
        </CardTitle>
        <CardDescription className="text-muted-foreground">
          {t("dashboard", "quickActionsDesc")}
        </CardDescription>
      </CardHeader>
      <CardContent>
        <div className="grid gap-3">
          {actions.map((action, index) => (
            <Button
              key={action.label}
              variant={action.variant}
              className={`
                btn-glass w-full justify-start group relative overflow-hidden
                ${action.variant === 'default' 
                  ? 'bg-gradient-to-r from-blue-500 to-purple-600 hover:from-blue-600 hover:to-purple-700 text-white border-0' 
                  : 'hover:scale-105'
                }
              `}
              style={{ animationDelay: `${index * 100}ms` }}
            >
              <div className="absolute inset-0 bg-gradient-to-r opacity-0 group-hover:opacity-10 transition-opacity duration-300" />
              <action.icon className={`mr-2 h-4 w-4 transition-transform group-hover:scale-110 ${
                action.variant === 'default' ? 'text-white' : `text-${action.gradient.split('-')[1]}-500`
              }`} />
              <span className="relative z-10">{action.label}</span>
            </Button>
          ))}
        </div>
      </CardContent>
    </Card>
  )
}
