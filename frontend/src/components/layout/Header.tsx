/**
 * Top bar: hamburger (mobile), breadcrumb, theme toggle, notifications, avatar.
 * Glassmorphism design with glow accents.
 */

import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useNavigate, useLocation } from "react-router-dom";
import { Menu, LogOut, Bell, Sun, Moon, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";

interface HeaderProps {
  onMenuClick?: () => void;
  notificationCount?: number;
}

const routeLabels: Record<string, string> = {
  "/dashboard": "nav.dashboard",
  "/products": "nav.products",
  "/competitors": "nav.competitors",
  "/alerts": "nav.alerts",
  "/digests": "nav.digests",
  "/import": "nav.import",
  "/analytics": "nav.analytics",
  "/ai": "nav.ai",
  "/settings": "nav.settings",
  "/admin": "nav.admin",
};

function Breadcrumb() {
  const { t } = useTranslation();
  const location = useLocation();
  const pathSegments = location.pathname.split("/").filter(Boolean);
  const currentLabel = routeLabels[`/${pathSegments[0]}`] ?? pathSegments[0];

  return (
    <nav className="hidden items-center gap-1.5 text-sm text-[var(--foreground-muted)] sm:flex">
      <span>{t("nav.dashboard")}</span>
      {pathSegments.length > 0 && pathSegments[0] !== "dashboard" && (
        <>
          <span>/</span>
          <span className="text-[var(--foreground)]">{t(currentLabel)}</span>
        </>
      )}
    </nav>
  );
}

export function Header({ onMenuClick, notificationCount = 0 }: HeaderProps) {
  const { t } = useTranslation();
  const { resolvedTheme, setTheme } = useTheme();
  const { user, logout } = useAuthStore();
  const navigate = useNavigate();

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
      className={cn(
        "flex h-14 min-h-[48px] shrink-0 items-center justify-between px-3 backdrop-blur-sm safe-area-top sm:h-16 sm:px-4 md:px-6",
        "bg-[var(--background-mid)] border-b border-[var(--glass-border)]"
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {onMenuClick && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 min-h-12 min-w-12 touch-manipulation md:hidden"
            onClick={onMenuClick}
            aria-label={t("common.menu")}
          >
            <Menu className="size-5" />
          </Button>
        )}
        <Breadcrumb />
      </div>
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "min-h-12 min-w-12 touch-manipulation sm:min-h-10 sm:min-w-10",
            "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]",
            "hover:shadow-[0_0_12px_var(--accent-glow)] transition-all duration-200"
          )}
          onClick={() => setTheme(isDark ? "light" : "dark")}
          aria-label={t("common.toggleTheme")}
        >
          {isDark ? (
            <Sun className="size-5 text-[var(--foreground)]" />
          ) : (
            <Moon className="size-5 text-[var(--foreground)]" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "relative min-h-12 min-w-12 touch-manipulation sm:min-h-10 sm:min-w-10",
            "bg-[var(--glass-bg)] border border-[var(--glass-border)] hover:border-[var(--glass-border-hover)]"
          )}
          aria-label={t("common.notifications")}
        >
          <Bell className="size-5 text-[var(--foreground)]" />
          {notificationCount > 0 && (
            <span
              className={cn(
                "absolute -top-0.5 -right-0.5 flex h-4 min-w-4 items-center justify-center rounded-full px-1 text-[10px] font-bold text-white",
                notificationCount > 0 && "glow-pulse"
              )}
              style={{
                background: "var(--accent)",
                boxShadow: "0 0 8px var(--accent-glow)",
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
              className="relative min-h-12 min-w-12 rounded-full touch-manipulation sm:min-h-10 sm:min-w-10 p-0"
              aria-label={t("auth.profile")}
            >
              <Avatar
                className="size-9 sm:size-9 ring-2 ring-[var(--accent)]"
                style={{ boxShadow: "0 0 12px var(--accent-glow)" }}
              >
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
            className="w-56 border-[var(--glass-border)] bg-[var(--glass-bg)] backdrop-blur-xl"
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
