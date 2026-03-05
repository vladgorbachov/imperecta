import { useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileSidebar } from "./MobileSidebar";
import { useSidebar } from "@/hooks/useSidebar";

/**
 * Main dashboard layout: CSS Grid with sidebar + main area.
 * Sidebar hidden on mobile (< md), visible md and above.
 * Header always visible. Main: scrollable with responsive padding.
 */
export function DashboardLayout() {
  const { isCollapsed, toggle } = useSidebar();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);

  return (
    <div className="grid h-screen grid-cols-[auto_1fr] grid-rows-[auto_1fr] bg-background text-foreground dark:bg-background dark:text-foreground">
      <aside className="col-span-1 row-span-2 hidden border-r border-border dark:border-border md:block">
        <Sidebar
          collapsed={isCollapsed}
          onToggle={toggle}
        />
      </aside>
      <Header onMenuClick={() => setMobileSheetOpen(true)} />
      <main className="col-span-1 min-h-0 overflow-auto p-3 md:p-6">
        <Outlet />
      </main>
      <MobileSidebar
        open={mobileSheetOpen}
        onOpenChange={setMobileSheetOpen}
      />
    </div>
  );
}
