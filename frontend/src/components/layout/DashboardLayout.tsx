/**
 * Main dashboard layout: sidebar + main area with ambient glow.
 * Glassmorphism design. Light theme: reduced blob opacity.
 */

import { useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { AnimatePresence, motion } from "framer-motion";
import { useTheme } from "next-themes";
import { Sidebar } from "./Sidebar";
import { Header } from "./Header";
import { MobileSidebar } from "./MobileSidebar";
import { BottomNavigation } from "./BottomNavigation";
import { SessionExpiryWarning } from "@/components/SessionExpiryWarning";
import { useSidebar } from "@/hooks/useSidebar";

export function DashboardLayout() {
  const { isCollapsed, toggle } = useSidebar();
  const [mobileSheetOpen, setMobileSheetOpen] = useState(false);
  const location = useLocation();
  const { resolvedTheme } = useTheme();
  const isLight = resolvedTheme === "light";
  const blobOpacity1 = isLight ? "0.04" : "0.06";
  const blobOpacity2 = isLight ? "0.02" : "0.04";

  return (
    <div
      className="grid h-[100dvh] min-h-screen grid-cols-[auto_1fr] grid-rows-[auto_1fr]"
      style={{
        background: "var(--background)",
        color: "var(--foreground)",
      }}
    >
      <aside className="col-span-1 row-span-2 hidden border-e md:block" style={{ borderColor: "var(--glass-border)" }}>
        <Sidebar collapsed={isCollapsed} onToggle={toggle} />
      </aside>
      <Header onMenuClick={() => setMobileSheetOpen(true)} />
      <main className="relative z-10 col-span-1 min-h-0 overflow-auto p-2.5 pb-16 safe-area-bottom-margin sm:pb-2.5">
        {/* Ambient background — decorative only */}
        <div className="pointer-events-none fixed inset-0 z-0 overflow-hidden">
          <div
            className="glow-dot glow-dot-accent"
            style={{ top: "-10%", right: "10%", opacity: blobOpacity1 }}
          />
          <div
            className="glow-dot glow-dot-accent2"
            style={{ bottom: "20%", left: "5%", opacity: blobOpacity2 }}
          />
        </div>

        <div className="relative z-[1] w-full">
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
      <MobileSidebar open={mobileSheetOpen} onOpenChange={setMobileSheetOpen} />
      <BottomNavigation />
      <SessionExpiryWarning />
    </div>
  );
}
