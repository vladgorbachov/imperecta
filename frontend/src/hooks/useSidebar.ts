import { useCallback, useEffect, useState } from "react";

const STORAGE_KEY = "imperecta_sidebar_collapsed";

/**
 * Manages sidebar collapsed state with localStorage persistence.
 * @returns { isCollapsed, toggle, setCollapsed }
 */
export function useSidebar() {
  const [isCollapsed, setIsCollapsed] = useState(() => {
    if (typeof window === "undefined") return false;
    const stored = localStorage.getItem(STORAGE_KEY);
    return stored === "true";
  });

  useEffect(() => {
    localStorage.setItem(STORAGE_KEY, String(isCollapsed));
  }, [isCollapsed]);

  const toggle = useCallback(() => {
    setIsCollapsed((prev) => !prev);
  }, []);

  const setCollapsed = useCallback((collapsed: boolean) => {
    setIsCollapsed(collapsed);
  }, []);

  return { isCollapsed, toggle, setCollapsed };
}
