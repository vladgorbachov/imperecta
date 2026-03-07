import { useTranslation } from "react-i18next";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Sidebar } from "./Sidebar";

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Mobile sidebar: Sheet from start (left in LTR, right in RTL).
 * Closes on nav item click (handled by Sidebar onNavigate).
 */
export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  const { t, i18n } = useTranslation();
  const isRtl = i18n.language === "ar";

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side={isRtl ? "right" : "left"}
        className="w-[256px] p-0"
      >
        <SheetHeader className="sr-only">
          <SheetTitle>{t("layout.navigation")}</SheetTitle>
        </SheetHeader>
        <Sidebar
          collapsed={false}
          onToggle={() => {}}
          isMobile
          onNavigate={() => onOpenChange(false)}
        />
      </SheetContent>
    </Sheet>
  );
}
