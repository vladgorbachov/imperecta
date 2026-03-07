import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileSidebar } from "./MobileSidebar";
import { SessionExpiryWarning } from "@/components/SessionExpiryWarning";
import { useSidebar } from "@/hooks/useSidebar";

/**
 * Main dashboard layout: CSS Grid with sidebar + main area.
 * Sidebar hidden on mobile (< md), visible md and above.
 * RTL: document.dir=rtl flips layout; border-inline-end for logical placement.
 */
export function DashboardLayout() {
  const { isCollapsed, toggle } = useSidebar();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  return (
    <div className="grid h-screen grid-cols-[auto_1fr] grid-rows-[auto_1fr] bg-background text-foreground dark:bg-background dark:text-foreground">
      <aside className="col-span-1 row-span-2 hidden border-e border-border dark:border-border md:block">
        <Sidebar
          collapsed={isCollapsed}
          onToggle={toggle}
        />
      </aside>
      <Header onMenuClick={() => setMobileSheetOpen(true)} />
      <main className="col-span-1 min-h-0 overflow-auto p-4 pb-6 sm:p-5 md:p-6 safe-area-bottom-margin scrollbar-hide">
        <Outlet />
      </main>
      <MobileSidebar
        open={mobileSheetOpen}
        onOpenChange={setMobileSheetOpen}
      />
      <SessionExpiryWarning />
    </div>
  );
}
