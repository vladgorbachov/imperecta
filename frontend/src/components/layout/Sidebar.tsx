import { Fragment } from "react";
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
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

const navItems = [
  { to: "/dashboard", icon: LayoutDashboard, key: "dashboard" },
  { to: "/products", icon: Package, key: "products" },
  { to: "/competitors", icon: Users, key: "competitors" },
  { to: "/alerts", icon: Bell, key: "alerts" },
  { to: "/digests", icon: FileText, key: "digests" },
  { to: "/import", icon: Upload, key: "import" },
  { to: "/settings", icon: Settings, key: "settings" },
] as const;

const TRIAL_TOTAL_DAYS = 14;
const TRIAL_DAYS_LEFT = 7;

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
  const location = useLocation();
  const showLabels = !collapsed || isMobile;
  const progressPercent = ((TRIAL_TOTAL_DAYS - TRIAL_DAYS_LEFT) / TRIAL_TOTAL_DAYS) * 100;

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
        {showLabels && (
          <span className="truncate font-display text-lg font-semibold text-primary dark:text-primary">
            {t("nav.logo")}
          </span>
        )}
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
              {showLabels && <span className="truncate">{t(`nav.${key}`)}</span>}
            </Link>
          );
          return collapsed && !isMobile ? (
            <Tooltip key={to}>
              <TooltipTrigger asChild>{linkEl}</TooltipTrigger>
              <TooltipContent side="right">{t(`nav.${key}`)}</TooltipContent>
            </Tooltip>
          ) : (
            <Fragment key={to}>{linkEl}</Fragment>
          );
        })}
      </nav>
      <div className="shrink-0 border-t border-border p-3 dark:border-border">
        <p className="mb-2 text-xs text-muted-foreground dark:text-muted-foreground">
          {showLabels ? t("layout.trialDaysLeft", { count: TRIAL_DAYS_LEFT }) : TRIAL_DAYS_LEFT}
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
