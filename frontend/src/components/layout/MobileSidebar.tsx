// MOBILE-2026: fully responsive + bottom nav + drawer

import { useTranslation } from "react-i18next";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Sidebar } from "./Sidebar";

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Mobile sidebar: Radix Sheet (Drawer) from start with backdrop-blur.
 * Closes on nav item click (handled by Sidebar onNavigate).
 */
export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  const { t, i18n } = useTranslation();
  const isRtl = i18n.language === "ar";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isRtl ? "right" : "left"}
        className="w-[min(256px,85vw)] max-w-[256px] border-e border-border/50 bg-card/95 p-0 backdrop-blur-xl dark:border-border/50 dark:bg-card/95"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>{t("layout.navigation")}</SheetTitle>
        </SheetHeader>
        <div className="pt-[env(safe-area-inset-top)] pb-[env(safe-area-inset-bottom)]">
          <Sidebar
            collapsed={false}
            onToggle={() => {}}
            isMobile
            onNavigate={() => onOpenChange(false)}
          />
        </div>
      </SheetContent>
    </Sheet>
  );
}
