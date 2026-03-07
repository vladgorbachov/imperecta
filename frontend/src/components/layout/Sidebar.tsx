import { Fragment, useMemo } from "react";
import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useAuthStore } from "@/stores/authStore";
import {
  LayoutDashboard,
  Package,
  Users,
  Bell,
  FileText,
  Upload,
  Settings,
  Shield,
  BarChart3,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "@/components/ui/button";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const baseNavItems = [
  { to: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
  { to: "/products", icon: Package, key: "products" },
  { to: "/competitors", icon: Users, key: "competitors" },
  { to: "/alerts", icon: Bell, key: "alerts" },
  { to: "/digests", icon: FileText, key: "digests" },
  { to: "/import", icon: Upload, key: "import" },
  { to: "/analytics", icon: BarChart3, key: "analytics" },
  { to: "/settings", icon: Settings, key: "settings" },
] as const;

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  isMobile?: boolean;
  onNavigate?: () => void;
}

/**
 * Desktop sidebar: logo, nav items, collapse button, trial indicator.
 * Expanded: w-60. Collapsed: w-16, icons only with tooltips.
 */
export function Sidebar({
  collapsed,
  onToggle,
  isMobile = false,
  onNavigate,
}: SidebarProps) {
  const { t } = useTranslation();
  const { resolvedTheme } = useTheme();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);
  const showLabels = !collapsed || isMobile;

  const navItems = useMemo(() => {
    const items = [...baseNavItems];
    if (user?.is_superuser) {
      const settingsIdx = items.findIndex((i) => i.key === "settings");
      items.splice(settingsIdx, 0, {
        to: "/admin",
        icon: Shield,
        key: "admin",
      });
    }
    return items;
  }, [user?.is_superuser]);

  const { trialDaysLeft, progressPercent } = useMemo(() => {
    const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
    const daysLeft = trialEndsAt
      ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / (24 * 60 * 60 * 1000)))
      : 0;
    const total = 14;
    const percent = trialEndsAt ? ((total - daysLeft) / total) * 100 : 0;
    return { trialDaysLeft: daysLeft, progressPercent: Math.min(100, percent) };
  }, [user?.trial_ends_at]);

  return (
    <aside
      className={cn(
        "flex flex-col border-r border-border bg-background text-foreground transition-[width] duration-300 ease-in-out dark:border-border dark:bg-background dark:text-foreground",
        isMobile ? "w-full" : collapsed ? "w-16" : "w-60"
      )}
    >
      <div
        className={cn(
          "flex h-16 shrink-0 items-center gap-2 border-b border-border px-4 dark:border-border",
          showLabels ? "justify-between" : "justify-center"
        )}
      >
        <img
          src={
            (resolvedTheme ?? "light") === "dark"
              ? "/images/logo-dark.png"
              : "/images/logo-light.png"
          }
          alt="Imperecta"
          className={cn(
            "object-contain object-left transition-opacity duration-200",
            showLabels ? "h-10 w-auto" : "h-8 w-8"
          )}
        />
        {!isMobile && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 text-muted-foreground hover:bg-accent hover:text-accent-foreground dark:text-muted-foreground dark:hover:bg-accent dark:hover:text-accent-foreground"
            onClick={onToggle}
            aria-label={collapsed ? t("common.expand") : t("common.collapse")}
          >
            {collapsed ? (
              <ChevronRight className="size-4" />
            ) : (
              <ChevronLeft className="size-4" />
            )}
          </Button>
        )}
      </div>
      <nav className="flex flex-1 flex-col gap-1 overflow-y-auto p-2">
        {navItems.map(({ to, icon: Icon, key }) => {
          const isAdmin = key === "admin";
          const navKey = isAdmin ? "admin" : key;
          const isActive = location.pathname === to || location.pathname.startsWith(to + "/");
          const linkClassName = cn(
            "flex items-center gap-3 rounded-md px-3 py-2 text-sm font-medium transition-colors duration-150",
            isActive
              ? "border-l-4 border-primary bg-accent/10 text-primary dark:border-primary dark:bg-accent/10 dark:text-primary"
              : "text-muted-foreground hover:bg-accent hover:text-accent-foreground dark:text-muted-foreground dark:hover:bg-accent dark:hover:text-accent-foreground",
            !showLabels && "justify-center px-2"
          );
          const linkEl = (
            <Link
              to={to}
              onClick={isMobile ? onNavigate : undefined}
              className={linkClassName}
            >
              <Icon className="size-5 shrink-0" />
              {showLabels && <span className="truncate">{t(`nav.${navKey}`)}</span>}
            </Link>
          );
          return collapsed && !isMobile ? (
            <Tooltip key={to}>
              <TooltipTrigger asChild>{linkEl}</TooltipTrigger>
              <TooltipContent side="right">{t(`nav.${navKey}`)}</TooltipContent>
            </Tooltip>
          ) : (
            <Fragment key={to}>{linkEl}</Fragment>
          );
        })}
      </nav>
      <div className="shrink-0 border-t border-border p-3 dark:border-border">
        <p className="mb-2 text-xs text-muted-foreground dark:text-muted-foreground">
          {showLabels ? t("layout.trialDaysLeft", { count: trialDaysLeft }) : trialDaysLeft}
        </p>
        <div className="mb-2 h-2 overflow-hidden rounded-full bg-muted dark:bg-muted">
          <div
            className="h-full rounded-full bg-primary transition-[width] dark:bg-primary"
            style={{ width: `${progressPercent}%` }}
          />
        </div>
        {showLabels && (
          <Button
            variant="secondary"
            size="sm"
            className="w-full text-xs"
          >
            {t("layout.upgrade")}
          </Button>
        )}
      </div>
    </aside>
  );
}
