/**
 * Top bar: hamburger (mobile), breadcrumb, theme toggle, notifications, avatar.
 * Glassmorphism design with glow accents.
 */

import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useNavigate } from "react-router-dom";
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
        "flex h-16 min-h-[56px] shrink-0 items-center justify-between px-4 backdrop-blur-xl safe-area-top sm:h-[4.5rem] sm:px-5 md:px-7",
        "bg-[var(--background-mid)] border-b border-[var(--glass-border)]"
      )}
    >
      <div className="flex min-w-0 flex-1 items-center gap-3">
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
      </div>
      <div className="flex shrink-0 items-center gap-2 sm:gap-2.5">
        <Button
          variant="ghost"
          size="icon"
          className={cn(
            "min-h-12 min-w-12 touch-manipulation sm:min-h-11 sm:min-w-11",
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
            "relative min-h-12 min-w-12 touch-manipulation sm:min-h-11 sm:min-w-11",
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
              className="relative min-h-12 min-w-12 rounded-full touch-manipulation sm:min-h-11 sm:min-w-11 p-0"
              aria-label={t("auth.profile")}
            >
              <Avatar
                className="size-10 sm:size-10 ring-2 ring-[var(--accent)]"
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
