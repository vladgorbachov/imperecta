import { Link, useLocation } from "react-router-dom"
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
import { cn } from "@/shared/utils/cn"
import { Button } from "@/shared/components/ui/button"
import { ScrollArea } from "@/shared/components/ui/scroll-area"
import { Logo } from "@/shared/components/ui/logo"

interface SidebarProps {
  open: boolean
  onOpenChange: (open: boolean) => void
}

export function Sidebar({ open, onOpenChange }: SidebarProps) {
  const location = useLocation()
  // const { t } = useLanguage()

  const routes = [
    {
      label: "Dashboard",
      icon: BarChart3,
      href: "/",
    },
    {
      label: "Projects",
      icon: ClipboardList,
      href: "/projects",
    },
    {
      label: "Tasks",
      icon: FileText,
      href: "/tasks",
    },
    {
      label: "Team",
      icon: Users,
      href: "/team",
    },
    {
      label: "Clients",
      icon: Building2,
      href: "/clients",
    },
    {
      label: "Finance",
      icon: DollarSign,
      href: "/finance",
    },
    {
      label: "Documents",
      icon: FileBox,
      href: "/documents",
    },
    {
      label: "Analytics",
      icon: PieChart,
      href: "/analytics",
    },
    {
      label: "Messages",
      icon: MessageSquare,
      href: "/messages",
    },
    {
      label: "Calendar",
      icon: Calendar,
      href: "/calendar",
    },
    {
      label: "Settings",
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
          "sidebar-glass fixed inset-y-0 left-0 z-50 w-61 p-6 shadow-lg transition-transform duration-300 lg:static lg:z-auto",
          open ? "translate-x-0" : "-translate-x-full lg:translate-x-0",
        )}
      >
        <div className="flex items-center justify-center mb-8">
          <Link to="/" className="flex items-center justify-center w-full">
            <Logo />
          </Link>
          <Button variant="ghost" size="icon" className="lg:hidden header-btn absolute right-0" onClick={() => onOpenChange(false)}>
            <X className="h-5 w-5" />
          </Button>
        </div>
        <ScrollArea className="h-[calc(100vh-7rem)] py-6">
          <nav className="flex flex-col gap-3 items-center">
            {routes.map((route) => (
              <Link
                key={route.href}
                to={route.href}
                className={cn(
                  "flex items-center justify-center gap-3 rounded-xl px-6 py-3 text-lg font-medium transition-all duration-300 group w-full text-center",
                  location.pathname === route.href 
                    ? "glass-card bg-gradient-to-r from-primary/20 to-primary/10 border-primary/30 text-black dark:text-white shadow-lg" 
                    : "hover:glass-card hover:bg-muted/50 hover:scale-105",
                )}
              >
                <route.icon className={cn(
                  "h-6 w-6 transition-colors",
                  location.pathname === route.href 
                    ? "text-primary" 
                    : "text-muted-foreground group-hover:text-foreground"
                )} />
                <span className="transition-colors text-center">
                  {route.label}
                </span>
              </Link>
            ))}
          </nav>
        </ScrollArea>
      </div>
    </>
  )
}
