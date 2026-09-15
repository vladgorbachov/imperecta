/**
 * Main dashboard layout: sidebar + header chrome around the routed content.
 * Graphite design language: flat surfaces, hairline borders.
 */

import { useEffect, useState } from "react";
import { Outlet } from "react-router-dom";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileSidebar } from "./MobileSidebar";
import { BottomNavigation } from "./BottomNavigation";
import { CommandPalette } from "@/components/CommandPalette";
import { SessionExpiryWarning } from "@/components/SessionExpiryWarning";
import { Scrollable } from "@/components/ui/Scrollable";
import { useSidebar } from "@/hooks/useSidebar";
import { usePaletteStore } from "@/stores/paletteStore";

export function DashboardLayout() {
  const { isCollapsed, toggle } = useSidebar();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);
  const paletteOpen = usePaletteStore((s) => s.open);
  const setPaletteOpen = usePaletteStore((s) => s.setOpen);
  const togglePalette = usePaletteStore((s) => s.toggle);

  useEffect(() => {
    const onKeyDown = (event: KeyboardEvent) => {
      if ((event.metaKey || event.ctrlKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        togglePalette();
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [togglePalette]);

  return (
    <div
      className="grid h-[100dvh] min-h-screen grid-cols-1 grid-rows-[auto_1fr] md:grid-cols-[auto_1fr]"
      style={{
        color: "var(--foreground)",
      }}
    >
      <aside className="col-span-1 row-span-2 hidden border-e md:block" style={{ borderColor: "var(--glass-border)" }}>
        <Sidebar collapsed={isCollapsed} onToggle={toggle} />
      </aside>
      <Header onMenuClick={() => setMobileSheetOpen(true)} />
      <main className="relative z-10 col-span-1 row-start-2 flex min-h-0 min-w-0 flex-col overflow-hidden md:row-auto">
        <Scrollable
          axis="y"
          outerClassName="min-h-0 min-w-0 flex-1"
          className="h-full w-full overflow-auto p-2.5 pb-16 safe-area-bottom-margin sm:pb-2.5"
        >
          <div className="relative z-[1] w-full min-w-0">
            <Outlet />
          </div>
        </Scrollable>
      </main>
      <MobileSidebar open={mobileSheetOpen} onOpenChange={setMobileSheetOpen} />
      <BottomNavigation />
      <CommandPalette open={paletteOpen} onOpenChange={setPaletteOpen} />
      <SessionExpiryWarning />
    </div>
  );
}
