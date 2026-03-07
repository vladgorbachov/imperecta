/**
 * Sectional sidebar with glass effect.
 * Sections: Core, Market Intelligence, Tools, Account, Admin (superuser).
 * Collapsed state persisted in localStorage "imperecta_sidebar_collapsed".
 */

import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Package,
  Users,
  Bell,
  FileText,
  Upload,
  Shield,
  TrendingUp,
  Bot,
  Sparkles,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible";
import {
  Tooltip,
  TooltipContent,
  TooltipTrigger,
} from "@/components/ui/tooltip";

interface SidebarProps {
  collapsed: boolean;
  onToggle: () => void;
  isMobile?: boolean;
  onNavigate?: () => void;
}

function SidebarLogo({
  collapsed,
  isMobile,
  onNavigate,
}: {
  collapsed: boolean;
  isMobile?: boolean;
  onNavigate?: () => void;
}) {
  const showLabels = !collapsed || isMobile;

  return (
    <Link
      to="/dashboard"
      onClick={isMobile ? onNavigate : undefined}
      className={cn(
        "flex h-16 shrink-0 items-center gap-2 border-b border-border/50 px-4 transition-colors hover:bg-accent/30 dark:border-border/50",
        showLabels ? "justify-start" : "justify-center"
      )}
    >
      <span
        className={cn(
          "font-display font-bold tracking-tight text-foreground",
          showLabels ? "text-lg" : "text-sm truncate"
        )}
      >
        {showLabels ? "Imperecta" : "I"}
      </span>
    </Link>
  );
}

function SparklesBadge({ className }: { className?: string }) {
  return (
    <Sparkles
      className={cn("size-3.5 shrink-0 text-primary group-hover:animate-pulse", className)}
      aria-hidden
    />
  );
}

interface SidebarItemProps {
  icon: React.ComponentType<{ className?: string }>;
  label: string;
  to: string;
  badge?: React.ReactNode;
  collapsed: boolean;
  isMobile?: boolean;
  onNavigate?: () => void;
  isActive: boolean;
}

function SidebarItem({
  icon: Icon,
  label,
  to,
  badge,
  collapsed,
  isMobile,
  onNavigate,
  isActive,
}: SidebarItemProps) {
  const showLabels = !collapsed || isMobile;

  const content = (
    <Link
      to={to}
      onClick={isMobile ? onNavigate : undefined}
      className={cn(
        "group relative flex items-center gap-3 rounded-md py-2.5 text-sm transition-colors",
        showLabels ? "ps-3 pe-3" : "justify-center ps-2 pe-2",
        isActive
          ? "bg-accent font-medium text-accent-foreground"
          : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
      )}
    >
      {isActive && (
        <motion.div
          layoutId="sidebar-active-indicator"
          className="absolute inset-y-1.5 start-0 w-[3px] rounded-e-full bg-primary"
          transition={{ type: "spring", stiffness: 500, damping: 30 }}
        />
      )}
      <Icon className="size-5 shrink-0" />
      {showLabels && (
        <>
          <span className="truncate flex-1">{label}</span>
          {badge}
        </>
      )}
    </Link>
  );

  if (collapsed && !isMobile) {
    return (
      <Tooltip>
        <TooltipTrigger asChild>{content}</TooltipTrigger>
        <TooltipContent side="right">{label}</TooltipContent>
      </Tooltip>
    );
  }

  return content;
}

interface SidebarSectionProps {
  label: string;
  collapsed: boolean;
  children: React.ReactNode;
  rightAction?: React.ReactNode;
}

function SidebarSection({ label, collapsed, children, rightAction }: SidebarSectionProps) {
  const showLabels = !collapsed;

  return (
    <Collapsible defaultOpen className="px-2">
      {showLabels && (
        <div className="flex w-full items-center justify-between gap-2 py-2">
          <CollapsibleTrigger
            className="flex flex-1 items-center text-left text-xs font-medium uppercase tracking-wider text-muted-foreground transition-colors hover:text-foreground"
          >
            {label}
          </CollapsibleTrigger>
          {rightAction}
        </div>
      )}
      <CollapsibleContent>
        <div className="space-y-0.5 py-1">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function SidebarFooter({
  collapsed,
  onToggle,
  isMobile,
}: {
  collapsed: boolean;
  onToggle: () => void;
  isMobile?: boolean;
}) {
  const { t } = useTranslation();
  const user = useAuthStore((s) => s.user);
  const showLabels = !collapsed || isMobile;

  const trialEndsAt = user?.trial_ends_at ? new Date(user.trial_ends_at) : null;
  const trialDaysLeft = trialEndsAt
    ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / (24 * 60 * 60 * 1000)))
    : 0;
  const isTrial = (user?.plan ?? "trial").toLowerCase() === "trial";

  return (
    <div className="shrink-0 border-t border-border/50 p-3 dark:border-border/50">
      {isTrial && (
        <p
          className={cn(
            "mb-2 text-xs text-muted-foreground",
            !showLabels && "text-center"
          )}
        >
          {showLabels
            ? t("layout.trialDaysLeft", { count: trialDaysLeft })
            : trialDaysLeft}
        </p>
      )}
      {!isMobile && collapsed && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-full text-muted-foreground hover:bg-accent/50 hover:text-foreground"
          onClick={onToggle}
          aria-label={t("common.expand")}
        >
          <ChevronRight className="size-4" />
        </Button>
      )}
    </div>
  );
}

export function Sidebar({
  collapsed,
  onToggle,
  isMobile = false,
  onNavigate,
}: SidebarProps) {
  const { t } = useTranslation();
  const location = useLocation();
  const user = useAuthStore((s) => s.user);

  const isActive = (path: string) =>
    location.pathname === path || location.pathname.startsWith(path + "/");

  return (
    <aside
      className={cn(
        "sidebar flex flex-col bg-card text-foreground transition-[width] duration-300 ease-in-out",
        "border-e border-border/50 dark:border-border/50",
        isMobile ? "w-full" : collapsed ? "w-16" : "w-[256px]"
      )}
    >
      <SidebarLogo collapsed={collapsed} isMobile={isMobile} onNavigate={onNavigate} />

      <nav className="flex flex-1 flex-col gap-2 overflow-y-auto py-4 scrollbar-hide">
        <SidebarSection
          label={t("nav.section.core")}
          collapsed={collapsed}
          rightAction={
            !isMobile ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                onClick={onToggle}
                aria-label={collapsed ? t("common.expand") : t("common.collapse")}
              >
                {collapsed ? (
                  <ChevronRight className="size-4" />
                ) : (
                  <ChevronLeft className="size-4" />
                )}
              </Button>
            ) : undefined
          }
        >
          <SidebarItem
            icon={LayoutDashboard}
            label={t("nav.dashboard")}
            to="/dashboard"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/dashboard")}
          />
          <SidebarItem
            icon={Package}
            label={t("nav.products")}
            to="/products"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/products")}
          />
          <SidebarItem
            icon={Users}
            label={t("nav.competitors")}
            to="/competitors"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/competitors")}
          />
        </SidebarSection>

        <SidebarSection label={t("nav.section.intelligence")} collapsed={collapsed}>
          <SidebarItem
            icon={TrendingUp}
            label={t("nav.analytics")}
            to="/analytics"
            badge={<SparklesBadge />}
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/analytics")}
          />
          <SidebarItem
            icon={Bell}
            label={t("nav.alerts")}
            to="/alerts"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/alerts")}
          />
          <SidebarItem
            icon={FileText}
            label={t("nav.digests")}
            to="/digests"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/digests")}
          />
        </SidebarSection>

        <SidebarSection label={t("nav.section.tools")} collapsed={collapsed}>
          <SidebarItem
            icon={Bot}
            label={t("nav.ai")}
            to="/ai"
            badge={<SparklesBadge />}
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/ai")}
          />
          <SidebarItem
            icon={Upload}
            label={t("nav.import")}
            to="/import"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/import")}
          />
        </SidebarSection>

        {user?.is_superuser && (
          <SidebarSection label={t("nav.section.admin")} collapsed={collapsed}>
            <SidebarItem
              icon={Shield}
              label={t("nav.admin")}
              to="/admin"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin")}
            />
          </SidebarSection>
        )}
      </nav>

      <SidebarFooter collapsed={collapsed} onToggle={onToggle} isMobile={isMobile} />
    </aside>
  );
}
