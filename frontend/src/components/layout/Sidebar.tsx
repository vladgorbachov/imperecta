/**
 * Sectional sidebar with glassmorphism design.
 * Sections: Core, Market Intelligence, Tools, Account, Admin (superuser).
 * Collapsed state persisted in localStorage "imperecta_sidebar_collapsed".
 */

import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Activity,
  Bell,
  DatabaseZap,
  Gauge,
  LayoutDashboard,
  Package,
  FileText,
  Scale,
  Shield,
  Store,
  Users,
  Bot,
  Sparkles,
  ChevronLeft,
  ChevronRight,
} from "lucide-react";
import { cn } from "@/lib/utils";
import { useAuthStore } from "@/stores/authStore";
import { Logo } from "./Logo";
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
  onToggle,
}: {
  collapsed: boolean;
  isMobile?: boolean;
  onNavigate?: () => void;
  onToggle?: () => void;
}) {
  const { t } = useTranslation();
  const showLabels = !collapsed || isMobile;

  return (
    <div
      className={cn(
        "relative flex h-16 shrink-0",
        showLabels
          ? "flex-row items-center justify-between px-4"
          : "flex-col items-center justify-center gap-0.5 px-0"
      )}
    >
      <Link
        to="/dashboard"
        onClick={isMobile ? onNavigate : undefined}
        className={cn(
          "flex items-center rounded-md transition-colors hover:bg-[var(--glass-bg-hover)]",
          showLabels ? "justify-start" : "justify-center"
        )}
      >
        <Logo collapsed={collapsed && !isMobile} />
      </Link>
      {!isMobile && (
        <Button
          variant="ghost"
          size="icon"
          className="size-8 min-w-8 shrink-0 text-[var(--foreground-muted)] hover:bg-[var(--glass-bg-hover)] hover:text-[var(--foreground)]"
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
  );
}

function SparklesBadge({ className }: { className?: string }) {
  return (
    <Sparkles
      className={cn("size-4 shrink-0 text-[var(--accent)]", className)}
      aria-hidden
    />
  );
}

interface SidebarItemProps {
  icon: React.ComponentType<{ className?: string; style?: React.CSSProperties }>;
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
        "group relative flex items-center gap-3 rounded-md py-2 text-sm transition-colors duration-150",
        showLabels ? "ps-4 pe-4" : "justify-center ps-3 pe-3",
        isActive
          ? "bg-[var(--accent-bg-subtle)] text-[var(--foreground)]"
          : "text-[var(--foreground-muted)] hover:bg-[var(--glass-bg-hover)] hover:text-[var(--foreground)]"
      )}
    >
      {isActive && (
        <div
          className="absolute inset-y-1.5 start-0 w-0.5 rounded-e-full"
          style={{ background: "var(--accent)" }}
        />
      )}
      <Icon
        className={cn(
          "size-5 shrink-0",
          isActive && "text-[var(--accent)]"
        )}
      />
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
        <TooltipContent side="right" className="surface-overlay">
          {label}
        </TooltipContent>
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
    <Collapsible defaultOpen className="px-2.5">
      {showLabels && (
        <div className="flex w-full items-center justify-between gap-2 py-2">
          <CollapsibleTrigger
            className="label-mono flex flex-1 items-center text-left transition-colors hover:text-[var(--foreground)]"
          >
            {label}
          </CollapsibleTrigger>
          {rightAction}
        </div>
      )}
      <CollapsibleContent>
        <div className="space-y-1 py-1">{children}</div>
      </CollapsibleContent>
    </Collapsible>
  );
}

function SidebarFooter({
  collapsed,
  isMobile,
}: {
  collapsed: boolean;
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
  const maxDays = 14;
  const progress = Math.min(100, (trialDaysLeft / maxDays) * 100);

  return (
    <div className="shrink-0 p-4">
      {isTrial && (
        <div className="surface-base overflow-hidden p-4">
          <p
            className={cn(
              "mb-3 text-sm text-[var(--foreground-muted)]",
              !showLabels && "text-center"
            )}
          >
            {showLabels
              ? t("layout.trialDaysLeft", { count: trialDaysLeft })
              : trialDaysLeft}
          </p>
          <div className="surface-sunken mb-4 h-1.5 w-full overflow-hidden rounded-full">
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "var(--accent)",
              }}
            />
          </div>
          <Button
            className="h-10 w-full font-semibold"
            style={{
              background: "var(--accent)",
              border: "none",
              color: "var(--primary-foreground)",
            }}
          >
            {t("layout.upgrade")}
          </Button>
        </div>
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
      data-sidebar
      className={cn(
        "flex flex-col text-[var(--foreground)] transition-[width] duration-300 ease-in-out",
        "border-e border-[var(--glass-border)]",
        isMobile ? "w-full" : collapsed ? "w-[72px]" : "w-[240px]"
      )}
    >
      <SidebarLogo
        collapsed={collapsed}
        isMobile={isMobile}
        onNavigate={onNavigate}
        onToggle={onToggle}
      />

      <nav className="flex flex-1 flex-col gap-2 overflow-y-auto py-4 text-sm">
        <SidebarSection label={t("nav.section.core")} collapsed={collapsed}>
          <SidebarItem
            icon={LayoutDashboard}
            label={t("nav.markets")}
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
        </SidebarSection>

        <SidebarSection label={t("nav.section.intelligence")} collapsed={collapsed}>
          <SidebarItem
            icon={Activity}
            label={t("nav.movements")}
            to="/movements"
            collapsed={collapsed}
            isMobile={isMobile}
            onNavigate={onNavigate}
            isActive={isActive("/movements")}
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
        </SidebarSection>

        {user?.is_superuser && (
          <SidebarSection label={t("nav.section.admin")} collapsed={collapsed}>
            <SidebarItem
              icon={Gauge}
              label={t("admin.tabs.ops")}
              to="/admin"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={
                location.pathname === "/admin" || location.pathname === "/admin/"
              }
            />
            <SidebarItem
              icon={DatabaseZap}
              label={t("admin.tabs.dataCollection")}
              to="/admin/data-collection"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin/data-collection")}
            />
            <SidebarItem
              icon={Store}
              label={t("admin.tabs.marketplacesTab")}
              to="/admin/overview"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin/overview")}
            />
            <SidebarItem
              icon={Users}
              label={t("admin.tabs.usersManagement")}
              to="/admin/users-management"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin/users-management")}
            />
            <SidebarItem
              icon={Shield}
              label={t("admin.alerts.tab")}
              to="/admin/alerts"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin/alerts")}
            />
            <SidebarItem
              icon={Scale}
              label={t("admin.tabs.compliance")}
              to="/admin/compliance"
              collapsed={collapsed}
              isMobile={isMobile}
              onNavigate={onNavigate}
              isActive={isActive("/admin/compliance")}
            />
          </SidebarSection>
        )}
      </nav>

      <SidebarFooter collapsed={collapsed} isMobile={isMobile} />
    </aside>
  );
}
