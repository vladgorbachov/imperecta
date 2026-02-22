import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  LayoutDashboard,
  Package,
  Users,
  Bell,
  FileText,
  Upload,
  Settings,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
  { to: "/products", icon: Package, key: "products" },
  { to: "/competitors", icon: Users, key: "competitors" },
  { to: "/alerts", icon: Bell, key: "alerts" },
  { to: "/digests", icon: FileText, key: "digests" },
  { to: "/import", icon: Upload, key: "import" },
  { to: "/settings", icon: Settings, key: "settings" },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  isMobile?: boolean;
  onNavigate?: () => void;
}

export function Sidebar({ collapsed, onToggle, isMobile = false, onNavigate }: SidebarProps) {
  const { t } = useTranslation();
  const location = useLocation();

  return (
    <aside
      className={cn(
        "flex flex-col border-r bg-[var(--sidebar)] text-[var(--sidebar-foreground)] transition-all duration-300",
        isMobile ? "w-full" : collapsed ? "w-16" : "w-64"
      )}
    >
      <div className="flex h-14 items-center justify-between border-b border-white/10 px-4">
        {!collapsed && !isMobile && (
          <span className="truncate font-semibold">PriceRadar</span>
        )}
        {!isMobile && (
          <Button
            variant="ghost"
            size="icon"
            className="text-white/80 hover:bg-white/10 hover:text-white"
            onClick={onToggle}
          >
            {collapsed ? (
              <ChevronRight className="size-4" />
            ) : (
              <ChevronLeft className="size-4" />
            )}
          </Button>
        )}
      </div>
      <nav className="flex flex-1 flex-col gap-1 p-2">
        {navItems.map(({ to, icon: Icon, key }) => {
          const isActive = location.pathname === to;
          return (
            <Link
              key={to}
              to={to}
              onClick={isMobile ? onNavigate : undefined}
              className={cn(
                "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors",
                isActive
                  ? "bg-indigo-500/20 text-white"
                  : "text-white/80 hover:bg-white/10 hover:text-white"
              )}
            >
              <Icon className="size-5 shrink-0" />
              {(!collapsed || isMobile) && <span>{t(`nav.${key}`)}</span>}
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
