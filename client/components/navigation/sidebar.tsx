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
import Image from "next/image"

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
          "sidebar-glass fixed inset-y-0 left-0 z-50 w-72 p-6 shadow-lg transition-transform duration-300 lg:static lg:z-auto",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-between mb-8">
          <Link href="/" className="flex items-center">
            <div className="logo-container">
              <Image 
                src="/logo.png" 
                alt="Imperecta" 
                width={32} 
                height={32}
                className="dark:invert"
              />
              <span className="ml-2 font-bold text-xl bg-gradient-to-r from-blue-600 via-purple-600 to-cyan-600 bg-clip-text text-transparent">
                Imperecta
              </span>
            </div>
          </Link>
          <Button variant="ghost" size="icon" className="lg:hidden btn-glass" onClick={() => onOpenChange(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <ScrollArea className="h-[calc(100vh-7rem)] py-6">
          <nav className="flex flex-col gap-3">
            {routes.map((route) => (
              <Link
                key={route.href}
                href={route.href}
                className={cn(
                  "flex items-center gap-3 rounded-xl px-4 py-3 text-sm font-medium transition-all duration-300 group",
                  pathname === route.href 
                    ? "glass-card bg-gradient-to-r from-primary/20 to-primary/10 border-primary/30 text-primary-foreground shadow-lg" 
                    : "hover:glass-card hover:bg-muted/50 hover:scale-105",
                )}
              >
                <route.icon className={cn(
                  "h-5 w-5 transition-colors",
                  pathname === route.href 
                    ? "text-primary" 
                    : "text-muted-foreground group-hover:text-foreground"
                )} />
                <span className="transition-colors">
                  {route.label}
                </span>
                {pathname === route.href && (
                  <div className="ml-auto w-2 h-2 rounded-full bg-gradient-to-r from-blue-500 to-purple-600 animate-pulse" />
                )}
              </Link>
            ))}
          </nav>
        </ScrollArea>
      </div>
    </>
  )
}
