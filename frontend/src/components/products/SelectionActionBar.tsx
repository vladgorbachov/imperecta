/**
 * Floating action bar shown when products are selected.
 * Displays count and delete button.
 */

import { Button } from "@/components/ui/button";
import { useTranslation } from "react-i18next";
import { Loader2, Trash2 } from "lucide-react";

interface SelectionActionBarProps {
  selectedCount: number;
  onDelete: () => void;
  onClear: () => void;
  isDeleting: boolean;
}

export function SelectionActionBar({
  selectedCount,
  onDelete,
  onClear,
  isDeleting,
}: SelectionActionBarProps) {
  const { t } = useTranslation();
  const label = t("products.selectedCount", { count: selectedCount });

  return (
    <div className="sticky bottom-0 z-10 flex flex-wrap items-center justify-between gap-3 border-t border-[var(--glass-border)] bg-[var(--background-elevated)]/95 px-4 py-3 backdrop-blur">
      <span className="text-sm font-medium">{label}</span>
      <div className="flex gap-2">
        <Button variant="outline" size="sm" onClick={onClear} disabled={isDeleting}>
          {t("products.clearSelection")}
        </Button>
        <Button
          variant="destructive"
          size="sm"
          onClick={onDelete}
          disabled={isDeleting}
        >
          {isDeleting ? (
            <Loader2 className="size-4 animate-spin" />
          ) : (
            <Trash2 className="size-4" />
          )}{" "}
          {t("products.deleteSelected")}
        </Button>
      </div>
    </div>
  );
}
