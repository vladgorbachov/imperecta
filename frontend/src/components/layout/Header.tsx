import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import { useLocation, useNavigate } from "react-router-dom";
import { Menu, LogOut, User, Settings, Bell, Sun, Moon } from "lucide-react";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";

const PATH_TO_NAV_KEY: Record<string, string> = {
  "/dashboard": "nav.dashboard",
  "/products": "nav.products",
  "/competitors": "nav.competitors",
  "/alerts": "nav.alerts",
  "/digests": "nav.digests",
  "/import": "nav.import",
  "/settings": "nav.settings",
};

function getBreadcrumbKey(pathname: string): string {
  const base = pathname.split("/").filter(Boolean)[0] ?? "";
  const path = base ? `/${base}` : "/dashboard";
  return PATH_TO_NAV_KEY[path] ?? "nav.dashboard";
}

const NOTIFICATION_COUNT = 3;

interface HeaderProps {
  onMenuClick?: () => void;
}

/**
 * Top bar: breadcrumb (left), theme toggle, language switcher, Bell with Badge, avatar dropdown.
 */
export function Header({ onMenuClick }: HeaderProps) {
  const { t } = useTranslation();
  const { resolvedTheme, setTheme } = useTheme();
  const { user, logout, updateLanguage } = useAuthStore();
  const navigate = useNavigate();
  const location = useLocation();
  const breadcrumbKey = getBreadcrumbKey(location.pathname);

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
    <header className="flex h-16 shrink-0 items-center justify-between border-b border-border bg-background px-4 dark:border-border dark:bg-background md:px-6">
      <div className="flex min-w-0 flex-1 items-center gap-2">
        {onMenuClick && (
          <Button
            variant="ghost"
            size="icon"
            className="shrink-0 md:hidden"
            onClick={onMenuClick}
            aria-label={t("common.menu")}
          >
            <Menu className="size-5" />
          </Button>
        )}
        <span className="truncate text-sm font-medium text-foreground dark:text-foreground">
          {t(breadcrumbKey)}
        </span>
      </div>
      <div className="flex shrink-0 items-center gap-2">
        <Button
          variant="ghost"
          size="icon"
          className="size-9"
          onClick={() => setTheme(isDark ? "light" : "dark")}
          aria-label={t("common.toggleTheme")}
        >
          {isDark ? (
            <Sun className="size-5 text-foreground dark:text-foreground" />
          ) : (
            <Moon className="size-5 text-foreground dark:text-foreground" />
          )}
        </Button>
        <LanguageSelector
          value={user?.language as import("@/i18n").LanguageCode}
          onChange={(code) => updateLanguage(code)}
          compact
          grouped={false}
        />
        <Button
          variant="ghost"
          size="icon"
          className="relative size-9"
          aria-label={t("common.notifications")}
        >
          <Bell className="size-5" />
          {NOTIFICATION_COUNT > 0 && (
            <Badge
              variant="destructive"
              className="absolute -right-1 -top-1 size-5 items-center justify-center rounded-full p-0 text-xs"
            >
              {NOTIFICATION_COUNT}
            </Badge>
          )}
        </Button>
        <DropdownMenu>
          <DropdownMenuTrigger asChild>
            <Button
              variant="ghost"
              className="relative size-9 rounded-full"
              aria-label={t("auth.profile")}
            >
              <Avatar className="size-9">
                <AvatarImage src="" alt={user?.name} />
                <AvatarFallback className="bg-primary text-primary-foreground">
                  {initials}
                </AvatarFallback>
              </Avatar>
            </Button>
          </DropdownMenuTrigger>
          <DropdownMenuContent align="end" className="w-56">
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <User className="mr-2 size-4" />
              {t("auth.profile")}
            </DropdownMenuItem>
            <DropdownMenuItem onClick={() => navigate("/settings")}>
              <Settings className="mr-2 size-4" />
              {t("nav.settings")}
            </DropdownMenuItem>
            <DropdownMenuSeparator />
            <DropdownMenuItem onClick={handleLogout}>
              <LogOut className="mr-2 size-4" />
              {t("auth.logout")}
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </div>
    </header>
  );
}
