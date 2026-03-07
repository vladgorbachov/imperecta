// MOBILE-2026: fully responsive + bottom nav + drawer

import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileSidebar } from "./MobileSidebar";
import { BottomNavigation } from "./BottomNavigation";
import { SessionExpiryWarning } from "@/components/SessionExpiryWarning";
import { useSidebar } from "@/hooks/useSidebar";

/**
 * Main dashboard layout: CSS Grid with sidebar + main area.
 * Sidebar hidden on mobile (< md), visible md and above.
 * Bottom nav visible only on mobile (< md).
 * RTL: document.dir=rtl flips layout; border-inline-end for logical placement.
 */
export function DashboardLayout() {
  const { isCollapsed, toggle } = useSidebar();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);
  const location = useLocation();

  return (
    <div className="grid h-[100dvh] min-h-screen grid-cols-[auto_1fr] grid-rows-[auto_1fr] bg-background text-foreground dark:bg-background dark:text-foreground">
      <aside className="col-span-1 row-span-2 hidden border-e border-border dark:border-border md:block">
        <Sidebar
          collapsed={isCollapsed}
          onToggle={toggle}
        />
      </aside>
      <Header onMenuClick={() => setMobileSheetOpen(true)} />
      <main className="col-span-1 min-h-0 overflow-auto px-4 pb-20 pt-4 sm:px-5 sm:pb-6 md:px-6 md:pb-6 safe-area-bottom-margin scrollbar-hide md:pb-6">
        <div className="mx-auto max-w-7xl">
          <AnimatePresence mode="wait">
            <motion.div
              key={location.pathname}
              initial={{ opacity: 0 }}
              animate={{ opacity: 1 }}
              exit={{ opacity: 0 }}
              transition={{ duration: 0.2 }}
            >
              <Outlet />
            </motion.div>
          </AnimatePresence>
        </div>
      </main>
      <MobileSidebar
        open={mobileSheetOpen}
        onOpenChange={setMobileSheetOpen}
      />
      <BottomNavigation />
      <SessionExpiryWarning />
    </div>
  );
}
