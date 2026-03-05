import { useTranslation } from "react-i18next";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Sidebar } from "./Sidebar";

interface MobileSidebarProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

/**
 * Mobile sidebar: Sheet from left with same content as Sidebar.
 * Closes on nav item click (handled by Sidebar onNavigate).
 */
export function MobileSidebar({ open, onOpenChange }: MobileSidebarProps) {
  const { t } = useTranslation();

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="left"
        className="w-60 p-0"
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
