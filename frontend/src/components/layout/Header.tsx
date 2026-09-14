/**
 * Top bar: hamburger (mobile), breadcrumb, theme toggle, notifications, avatar.
 * Glassmorphism design with glow accents.
 */

import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useLocation, useNavigate } from "react-router-dom";
import { Menu, LogOut, Bell, Sun, Moon, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { DashboardHeaderCountrySelector } from "@/components/dashboard/DashboardHeaderCountrySelector";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { HeaderTicker } from "./HeaderTicker";
import { cn } from "@/lib/utils";

interface HeaderProps {
  onMenuClick?: () => void;
  notificationCount?: number;
}

export function Header({ onMenuClick, notificationCount = 0 }: HeaderProps) {
  const { t } = useTranslation();
  const { resolvedTheme, setTheme } = useTheme();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const isDashboardRoute =
    location.pathname === "/dashboard" || location.pathname.endsWith("/dashboard");

  const handleLogout = () => {
    logout();
    navigate("/login");
  };

  const initials = user?.name
    ? user.name
        .split(" ")
        .map((n) => n[0])
        .join("")
        .toUpperCase()
        .slice(0, 2)
    : user?.email?.[0]?.toUpperCase() ?? "?";

  const isDark = resolvedTheme === "dark";

  return (
    <header
      className="flex h-16 min-h-[44px] min-w-0 shrink-0 items-center gap-1.5 overflow-hidden border-b border-[var(--glass-border)] px-3 safe-area-top sm:gap-2 sm:px-4 md:px-5"
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {onMenuClick && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 min-h-10 min-w-10 touch-manipulation md:hidden"
            onClick={onMenuClick}
            aria-label={t("common.menu")}
          >
            <Menu className="size-4" />
          </Button>
        )}
        <HeaderTicker className="min-w-0 flex-1" />
      </div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        {isDashboardRoute ? <DashboardHeaderCountrySelector /> : null}
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "min-h-9 min-w-9 size-9 touch-manipulation",
            "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]",
            "transition-colors duration-150"
          )}
          onClick={() => setTheme(isDark ? "light" : "dark")}
          aria-label={t("common.toggleTheme")}
        >
          {isDark ? (
            <Sun className="size-4 text-[var(--foreground)]" />
          ) : (
            <Moon className="size-4 text-[var(--foreground)]" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "relative min-h-9 min-w-9 size-9 touch-manipulation transition-colors",
            "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]"
          )}
          aria-label={t("common.notifications")}
        >
          <Bell className="size-4 text-[var(--foreground)]" />
          {notificationCount > 0 && (
            <span
              className="absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-2xs font-bold"
              style={{
                background: "var(--accent)",
                color: "var(--primary-foreground)",
              }}
            >
              {notificationCount > 99 ? "99+" : notificationCount}
            </span>
          )}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="relative min-h-9 min-w-9 size-9 rounded-full touch-manipulation p-0"
              aria-label={t("auth.profile")}
            >
              <Avatar className="size-8 ring-1 ring-[var(--glass-border-hover)]">
                <AvatarImage src={user?.avatar_url ?? undefined} alt={user?.name} />
                <AvatarFallback
                  className="text-[var(--foreground)]"
                  style={{ background: "var(--glass-bg)" }}
                >
                  {initials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            align="end"
            className="w-56 surface-overlay"
          >
            <div className="px-2 py-2">
              <p className="truncate text-sm font-medium text-[var(--foreground)]">
                {user?.name ?? "—"}
              </p>
              <p className="truncate text-xs text-[var(--foreground-muted)]">
                {user?.email ?? "—"}
              </p>
            </div>
            <DropdownMenuSeparator className="bg-[var(--glass-border)]" />
            <DropdownMenuItem
              onClick={() => navigate("/settings")}
              className="focus:bg-[var(--glass-bg-hover)] focus:text-[var(--foreground)]"
            >
              <Settings className="me-2 size-4" />
              {t("nav.settings")}
            </DropdownMenuItem>
            <DropdownMenuItem
              onClick={handleLogout}
              className="focus:bg-[var(--glass-bg-hover)] focus:text-[var(--foreground)]"
            >
              <LogOut className="me-2 size-4" />
              {t("auth.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
