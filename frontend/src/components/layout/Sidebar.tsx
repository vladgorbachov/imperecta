/**
 * Sectional sidebar with glassmorphism design.
 * Sections: Core, Market Intelligence, Tools, Account, Admin (superuser).
 * Collapsed state persisted in localStorage "imperecta_sidebar_collapsed".
 */

import { Link, useLocation } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
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
  const { resolvedTheme } = useTheme();
  const isDark = resolvedTheme === "dark";
  const logoSrc = isDark ? "/images/logo_dark.png" : "/images/logo_light.png";

  return (
    <Link
      to="/dashboard"
      onClick={isMobile ? onNavigate : undefined}
      className={cn(
        "flex h-16 shrink-0 items-stretch border-b px-0 transition-colors",
        "border-[var(--glass-border)] hover:bg-[var(--glass-bg-hover)]",
        showLabels ? "justify-start" : "justify-center"
      )}
    >
      <img
        src={logoSrc}
        alt="Imperecta"
        className="h-full w-full object-fill object-left"
      />
    </Link>
  );
}

function SparklesBadge({ className }: { className?: string }) {
  return (
    <Sparkles
      className={cn("size-3.5 shrink-0 text-[var(--accent)]", className)}
      style={{ filter: "drop-shadow(0 0 4px var(--accent-glow))" }}
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
        "group relative flex items-center gap-3 rounded-lg py-3 text-sm transition-all duration-200",
        showLabels ? "ps-3.5 pe-3.5" : "justify-center ps-2.5 pe-2.5",
        isActive
          ? "bg-gradient-to-r from-[var(--accent-bg-subtle)] to-transparent text-[var(--foreground)]"
          : "text-[var(--foreground-muted)] hover:bg-[var(--glass-bg-hover)] hover:text-[var(--foreground)]"
      )}
    >
      {isActive && (
        <div
          className="absolute inset-y-1.5 start-0 w-[3px] rounded-e-full"
          style={{
            background: "var(--accent)",
            boxShadow: "0 0 8px var(--accent-glow)",
          }}
        />
      )}
      <Icon
        className={cn(
          "size-5 shrink-0",
          isActive && "text-[var(--accent)]"
        )}
        style={
          isActive
            ? { filter: "drop-shadow(0 0 6px var(--accent-glow))" }
            : undefined
        }
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
        <TooltipContent side="right" className="glass-card border-[var(--glass-border)]">
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
    <Collapsible defaultOpen className="px-2">
      {showLabels && (
        <div className="flex w-full items-center justify-between gap-2 py-2.5">
          <CollapsibleTrigger
            className="flex flex-1 items-center text-left text-xs font-medium uppercase tracking-wider text-[var(--foreground-muted)] transition-colors hover:text-[var(--foreground)]"
          >
            {label}
          </CollapsibleTrigger>
          {rightAction}
        </div>
      )}
      <CollapsibleContent>
        <div className="space-y-1 py-1.5">{children}</div>
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
  const maxDays = 14;
  const progress = Math.min(100, (trialDaysLeft / maxDays) * 100);

  return (
    <div className="shrink-0 border-t border-[var(--glass-border)] p-3">
      {isTrial && (
        <div className="glass-card overflow-hidden p-3">
          <p
            className={cn(
              "mb-2 text-xs text-[var(--foreground-muted)]",
              !showLabels && "text-center"
            )}
          >
            {showLabels
              ? t("layout.trialDaysLeft", { count: trialDaysLeft })
              : trialDaysLeft}
          </p>
          <div
            className="mb-3 h-1.5 w-full overflow-hidden rounded-full bg-[var(--glass-bg)]"
            style={{ border: "1px solid var(--glass-border)" }}
          >
            <div
              className="h-full rounded-full transition-all duration-500"
              style={{
                width: `${progress}%`,
                background: "linear-gradient(90deg, var(--accent), var(--accent2))",
                boxShadow: "0 0 8px var(--accent-glow)",
              }}
            />
          </div>
          <Button
            className="w-full font-semibold"
            style={{
              background: "linear-gradient(135deg, var(--accent-dim), var(--accent))",
              boxShadow: "0 0 16px var(--accent-glow)",
              border: "none",
              color: "var(--primary-foreground)",
            }}
          >
            {t("layout.upgrade")}
          </Button>
        </div>
      )}
      {!isMobile && collapsed && (
        <Button
          variant="ghost"
          size="icon"
          className="h-8 w-full text-[var(--foreground-muted)] hover:bg-[var(--glass-bg-hover)] hover:text-[var(--foreground)]"
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
      data-sidebar
      className={cn(
        "flex flex-col text-[var(--foreground)] transition-[width] duration-300 ease-in-out",
        "border-e border-[var(--glass-border)]",
        isMobile ? "w-full" : collapsed ? "w-[72px]" : "w-[280px]"
      )}
    >
      <SidebarLogo collapsed={collapsed} isMobile={isMobile} onNavigate={onNavigate} />

      <nav className="flex flex-1 flex-col gap-2 overflow-y-auto py-4">
        <SidebarSection
          label={t("nav.section.core")}
          collapsed={collapsed}
          rightAction={
            !isMobile ? (
              <Button
                variant="ghost"
                size="icon"
                className="h-7 w-7 shrink-0 text-[var(--foreground-muted)] hover:bg-[var(--glass-bg-hover)] hover:text-[var(--foreground)]"
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
