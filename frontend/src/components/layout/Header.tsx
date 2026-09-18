/**
 * Top bar: hamburger (mobile), page slot, theme toggle, notifications, avatar.
 * The left side is a portal target (#header-page-slot) pages fill with their
 * own controls — the dashboard mounts its ScopeBar there, so scope and chrome
 * share one header row instead of stacking two bars.
 */

import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useNavigate } from "react-router-dom";
import { Menu, LogOut, Search, Sun, Moon, Settings } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { usePaletteStore } from "@/stores/paletteStore";
import { NotificationsMenu } from "@/components/layout/NotificationsMenu";
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
}

export function Header({ onMenuClick }: HeaderProps) {
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
      className="flex h-16 min-h-[44px] min-w-0 shrink-0 items-center gap-1.5 overflow-hidden border-b border-[var(--glass-border)] px-3 safe-area-top sm:gap-2 sm:px-4 md:px-5"
    >
      <div id="header-page-slot" className="flex min-w-0 flex-1 items-center gap-2">
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
      </div>
      <div className="flex shrink-0 items-center gap-1.5 sm:gap-2">
        <button
          type="button"
          onClick={() => usePaletteStore.getState().setOpen(true)}
          className="hidden h-9 items-center gap-2 rounded-md border border-[var(--glass-border)] bg-[var(--glass-bg)] px-3 text-sm text-[var(--foreground-muted)] transition-colors hover:border-[var(--glass-border-hover)] hover:text-[var(--foreground)] sm:flex"
          aria-label={t("palette.placeholder")}
        >
          <Search className="size-3.5" />
          <span className="hidden md:inline">{t("palette.hint")}</span>
          <kbd className="label-mono rounded border border-[var(--glass-border)] px-1 py-px">⌘K</kbd>
        </button>
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
        <NotificationsMenu />
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
