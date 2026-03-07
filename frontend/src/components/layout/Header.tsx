// MOBILE-2026: fully responsive + bottom nav + drawer

import { Link } from "react-router-dom";
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

interface HeaderProps {
  onMenuClick?: () => void;
}

/**
 * Top bar: hamburger (mobile), logo always visible, theme toggle, notifications, avatar.
 * Touch targets min 48px (min-h-12 min-w-12).
 */
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
    <header className="flex h-14 min-h-[48px] shrink-0 items-center justify-between border-b border-border bg-background/95 px-3 backdrop-blur-sm safe-area-top sm:h-16 sm:px-4 dark:border-border dark:bg-background/95 md:px-6">
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
        <Link
          to="/dashboard"
          className="font-display text-lg font-bold tracking-tight text-foreground truncate min-w-0"
        >
          Imperecta
        </Link>
      </div>
      <div className="flex shrink-0 items-center gap-1 sm:gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="min-h-12 min-w-12 touch-manipulation sm:min-h-10 sm:min-w-10"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          aria-label={t("common.toggleTheme")}
        >
          {isDark ? (
            <Sun className="size-5 text-foreground dark:text-foreground" />
          ) : (
            <Moon className="size-5 text-foreground dark:text-foreground" />
          )}
        </Button>
        <Button
          variant="ghost"
          size="icon"
          className="relative min-h-12 min-w-12 touch-manipulation sm:min-h-10 sm:min-w-10"
          aria-label={t("common.notifications")}
        >
          <Bell className="size-5" />
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="relative min-h-12 min-w-12 rounded-full touch-manipulation sm:min-h-10 sm:min-w-10"
              aria-label={t("auth.profile")}
            >
              <Avatar className="size-9 sm:size-9">
                <AvatarImage src={user?.avatar_url ?? undefined} alt={user?.name} />
                <AvatarFallback className="bg-primary text-primary-foreground">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <div className="px-2 py-2">
              <p className="truncate text-sm font-medium text-foreground">
                {user?.name ?? "—"}
              </p>
              <p className="truncate text-xs text-muted-foreground">
                {user?.email ?? "—"}
              </p>
            </div>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings className="me-2 size-4" />
              {t("nav.settings")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="me-2 size-4" />
              {t("auth.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
