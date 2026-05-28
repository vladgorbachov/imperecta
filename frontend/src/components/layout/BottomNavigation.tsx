// MOBILE-2026: fully responsive + bottom nav + drawer

import { useTranslation } from "react-i18next";
import { useLocation, useNavigate } from "react-router-dom";
import { motion } from "framer-motion";
import {
  LayoutDashboard,
  Package,
  TrendingUp,
  Bot,
} from "lucide-react";
import { cn } from "@/lib/utils";

const NAV_ITEMS = [
  { path: "/dashboard", icon: LayoutDashboard, i18nKey: "nav.markets" },
  { path: "/products", icon: Package, i18nKey: "nav.products" },
  { path: "/analytics", icon: TrendingUp, i18nKey: "nav.analytics" },
  { path: "/ai", icon: Bot, i18nKey: "nav.ai" },
] as const;

/**
 * Bottom navigation bar: visible only on mobile (< md).
 * 5 main sections with active glow effect.
 * Touch targets min 48px.
 */
export function BottomNavigation() {
  const { t } = useTranslation();
  const location = useLocation();
  const navigate = useNavigate();

  return (
    <nav
      className="fixed inset-x-0 bottom-0 z-40 flex items-center justify-around border-t border-border bg-background/95 px-2 pb-[env(safe-area-inset-bottom)] pt-2 backdrop-blur-xl md:hidden dark:border-border dark:bg-background/95"
      aria-label="Main navigation"
    >
      {NAV_ITEMS.map(({ path, icon: Icon, i18nKey }) => {
        const isActive =
          location.pathname === path ||
          (path !== "/dashboard" && location.pathname.startsWith(path));
        return (
          <button
            key={path}
            type="button"
            onClick={() => navigate(path)}
            className={cn(
              "relative flex min-h-12 min-w-12 flex-col items-center justify-center gap-0.5 rounded-xl transition-colors active:scale-95",
              "touch-manipulation select-none",
              isActive
                ? "text-primary"
                : "text-muted-foreground hover:text-foreground"
            )}
            aria-label={t(i18nKey)}
            aria-current={isActive ? "page" : undefined}
          >
            {isActive && (
              <motion.div
                layoutId="bottom-nav-active"
                className="absolute inset-0 rounded-xl bg-primary/10"
                transition={{ type: "spring", stiffness: 500, damping: 30 }}
              />
            )}
            <Icon
              className={cn(
                "relative z-10 size-6 shrink-0",
                isActive && "drop-shadow-[0_0_6px_hsl(var(--primary)/0.5)]"
              )}
            />
            <span className="relative z-10 truncate text-[10px] font-medium">
              {t(i18nKey)}
            </span>
          </button>
        );
      })}
    </nav>
  );
}
