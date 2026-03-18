import { useState, useCallback, useEffect } from "react";

interface UseRowSelectionOptions<T extends string | number> {
  /** All item IDs on current page */
  pageItemIds: T[];
}

export function useRowSelection<T extends string | number>({
  pageItemIds,
}: UseRowSelectionOptions<T>) {
  const [selectedIds, setSelectedIds] = useState<Set<T>>(new Set());

  const toggleItem = useCallback((id: T) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) {
        next.delete(id);
      } else {
        next.add(id);
      }
      return next;
    });
  }, []);

  const selectAll = useCallback(() => {
    setSelectedIds(new Set(pageItemIds));
  }, [pageItemIds]);

  const clearSelection = useCallback(() => {
    setSelectedIds(new Set());
  }, []);

  const isAllSelected =
    pageItemIds.length > 0 && pageItemIds.every((id) => selectedIds.has(id));

  const toggleAll = useCallback(() => {
    if (isAllSelected) {
      setSelectedIds(new Set());
    } else {
      setSelectedIds(new Set(pageItemIds));
    }
  }, [isAllSelected, pageItemIds]);

  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key === "a") {
        const tag = (e.target as HTMLElement)?.tagName;
        if (tag !== "INPUT" && tag !== "TEXTAREA") {
          e.preventDefault();
          selectAll();
        }
      }
      if (e.key === "Escape") {
        clearSelection();
      }
    };

    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, [selectAll, clearSelection]);

  return {
    selectedIds,
    selectedCount: selectedIds.size,
    toggleItem,
    selectAll,
    clearSelection,
    toggleAll,
    isAllSelected,
    isSelected: (id: T) => selectedIds.has(id),
  };
}
