"use client"
import Link from "next/link"
import { usePathname } from "next/navigation"
import {
  BarChart3,
  Users,
  ClipboardList,
  MessageSquare,
  Calendar,
  Settings,
  X,
  Building2,
  FileText,
  DollarSign,
  FileBox,
  PieChart,
} from "lucide-react"
import { cn } from "@/client/utils/cn"
import { Button } from "@/client/components/ui/button"
import { ScrollArea } from "@/client/components/ui/scroll-area"
import { useLanguage } from "@/client/i18n/language-context"
import { Logo } from "@/client/components/ui/logo"

interface SidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function Sidebar({ open, onOpenChange }: SidebarProps) {
  const pathname = usePathname()
  const { t } = useLanguage()

  const routes = [
    {
      label: t("common", "dashboard"),
      icon: BarChart3,
      href: "/",
    },
    {
      label: t("common", "projects"),
      icon: ClipboardList,
      href: "/projects",
    },
    {
      label: t("common", "tasks"),
      icon: FileText,
      href: "/tasks",
    },
    {
      label: t("common", "team"),
      icon: Users,
      href: "/team",
    },
    {
      label: t("common", "clients"),
      icon: Building2,
      href: "/clients",
    },
    {
      label: t("common", "finance"),
      icon: DollarSign,
      href: "/finance",
    },
    {
      label: t("common", "documents"),
      icon: FileBox,
      href: "/documents",
    },
    {
      label: t("common", "analytics"),
      icon: PieChart,
      href: "/analytics",
    },
    {
      label: t("common", "messages"),
      icon: MessageSquare,
      href: "/messages",
    },
    {
      label: t("common", "calendar"),
      icon: Calendar,
      href: "/calendar",
    },
    {
      label: t("common", "settings"),
      icon: Settings,
      href: "/settings",
    },
  ]

  return (
    <>
      <div
        className={cn("fixed inset-0 z-40 bg-background/80 backdrop-blur-sm lg:hidden", open ? "block" : "hidden")}
        onClick={() => onOpenChange(false)}
      />
      <div
        className={cn(
          "fixed inset-y-0 left-0 z-50 w-72 border-r bg-card p-6 shadow-lg transition-transform duration-300 lg:static lg:z-auto",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-between mb-6">
          <Link href="/" className="flex items-center">
            <Logo />
          </Link>
          <Button variant="ghost" size="icon" className="lg:hidden" onClick={() => onOpenChange(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <ScrollArea className="h-[calc(100vh-5rem)] py-6">
          <nav className="flex flex-col gap-2">
            {routes.map((route) => (
              <Link
                key={route.href}
                href={route.href}
                className={cn(
                  "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                  pathname === route.href ? "bg-primary text-primary-foreground" : "hover:bg-muted",
                )}
              >
                <route.icon className="h-5 w-5" />
                {route.label}
              </Link>
            ))}
          </nav>
        </ScrollArea>
      </div>
    </>
  )
}
