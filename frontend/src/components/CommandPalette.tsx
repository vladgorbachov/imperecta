/**
 * Global command palette (Cmd/Ctrl+K).
 * One field for navigation, quick actions and product search.
 * Product search reuses GET /pool/products (no new backend).
 */

import {
  useCallback,
  useEffect,
  useMemo,
  useRef,
  useState,
  type ComponentType,
} from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import { useTheme } from "next-themes";
import {
  Activity,
  Bell,
  Bot,
  FileText,
  LayoutDashboard,
  Moon,
  Package,
  Search,
  Settings,
  Shield,
  Sun,
} from "lucide-react";
import * as DialogPrimitive from "@radix-ui/react-dialog";
import { usePoolProducts } from "@/hooks/usePoolProducts";
import { useDebounce } from "@/hooks/useDebounce";
import { useAuthStore } from "@/stores/authStore";
import { cn } from "@/lib/utils";

interface PaletteEntry {
  id: string;
  section: "pages" | "actions" | "products";
  label: string;
  hint?: string;
  icon?: ComponentType<{ className?: string }>;
  run: () => void;
}

export interface CommandPaletteProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function CommandPalette({ open, onOpenChange }: CommandPaletteProps) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { resolvedTheme, setTheme } = useTheme();
  const user = useAuthStore((s) => s.user);

  const [query, setQuery] = useState("");
  const [activeIndex, setActiveIndex] = useState(0);
  const listRef = useRef<HTMLDivElement | null>(null);
  const debouncedQuery = useDebounce(query, 300);

  const productSearchEnabled = open && debouncedQuery.trim().length >= 2;
  const { data: productData } = usePoolProducts(
    {
      search: productSearchEnabled ? debouncedQuery.trim() : undefined,
      limit: 6,
      offset: 0,
    },
    { enabled: productSearchEnabled, liveRefresh: false },
  );

  const close = useCallback(() => {
    onOpenChange(false);
    setQuery("");
    setActiveIndex(0);
  }, [onOpenChange]);

  const go = useCallback(
    (to: string) => {
      close();
      navigate(to);
    },
    [close, navigate],
  );

  const entries = useMemo((): PaletteEntry[] => {
    const q = query.trim().toLowerCase();

    const pages: PaletteEntry[] = [
      { id: "p-dashboard", section: "pages", label: t("nav.markets"), icon: LayoutDashboard, run: () => go("/dashboard") },
      { id: "p-products", section: "pages", label: t("nav.products"), icon: Package, run: () => go("/products") },
      { id: "p-movements", section: "pages", label: t("nav.movements"), icon: Activity, run: () => go("/movements") },
      { id: "p-alerts", section: "pages", label: t("nav.alerts"), icon: Bell, run: () => go("/alerts") },
      { id: "p-digests", section: "pages", label: t("nav.digests"), icon: FileText, run: () => go("/digests") },
      { id: "p-ai", section: "pages", label: t("nav.ai"), icon: Bot, run: () => go("/ai") },
      { id: "p-settings", section: "pages", label: t("nav.settings"), icon: Settings, run: () => go("/settings") },
      ...(user?.is_superuser
        ? [{ id: "p-admin", section: "pages" as const, label: t("nav.admin"), icon: Shield, run: () => go("/admin") }]
        : []),
    ];

    const isDark = resolvedTheme === "dark";
    const actions: PaletteEntry[] = [
      {
        id: "a-theme",
        section: "actions",
        label: t("palette.toggleTheme"),
        icon: isDark ? Sun : Moon,
        run: () => {
          setTheme(isDark ? "light" : "dark");
          close();
        },
      },
      {
        id: "a-ask",
        section: "actions",
        label: t("palette.askAi"),
        icon: Bot,
        run: () => go("/ai"),
      },
    ];

    const filtered = (items: PaletteEntry[]) =>
      q === "" ? items : items.filter((item) => item.label.toLowerCase().includes(q));

    const products: PaletteEntry[] = productSearchEnabled
      ? (productData?.items ?? []).map((item) => ({
          id: `prod-${item.id}`,
          section: "products" as const,
          label: item.title ?? item.url,
          hint: item.marketplace_name ?? item.marketplace_domain ?? undefined,
          run: () =>
            go(`/products?search=${encodeURIComponent(debouncedQuery.trim())}`),
        }))
      : [];

    return [...filtered(pages), ...filtered(actions), ...products];
  }, [
    query,
    t,
    user?.is_superuser,
    resolvedTheme,
    setTheme,
    go,
    close,
    productSearchEnabled,
    productData?.items,
    debouncedQuery,
  ]);

  useEffect(() => {
    setActiveIndex(0);
  }, [query, open]);

  const onKeyDown = (event: React.KeyboardEvent) => {
    if (event.key === "ArrowDown") {
      event.preventDefault();
      setActiveIndex((index) => Math.min(index + 1, entries.length - 1));
    } else if (event.key === "ArrowUp") {
      event.preventDefault();
      setActiveIndex((index) => Math.max(index - 1, 0));
    } else if (event.key === "Enter") {
      event.preventDefault();
      entries[activeIndex]?.run();
    }
  };

  useEffect(() => {
    const active = listRef.current?.querySelector('[data-active="true"]');
    active?.scrollIntoView({ block: "nearest" });
  }, [activeIndex]);

  const sections: Array<{ key: PaletteEntry["section"]; label: string }> = [
    { key: "pages", label: t("palette.pages") },
    { key: "actions", label: t("palette.actions") },
    { key: "products", label: t("palette.products") },
  ];

  return (
    <DialogPrimitive.Root open={open} onOpenChange={(next) => (next ? onOpenChange(true) : close())}>
      <DialogPrimitive.Portal>
        <DialogPrimitive.Overlay className="fixed inset-0 z-50 bg-black/50" />
        <DialogPrimitive.Content
          className="surface-overlay fixed left-1/2 top-[15vh] z-50 w-[min(560px,calc(100vw-2rem))] -translate-x-1/2 overflow-hidden rounded-xl p-0"
          onKeyDown={onKeyDown}
        >
          <DialogPrimitive.Title className="sr-only">
            {t("palette.placeholder")}
          </DialogPrimitive.Title>
          <div className="flex items-center gap-2 border-b border-[var(--glass-border)] px-4">
            <Search className="size-4 shrink-0 text-muted-foreground" />
            <input
              autoFocus
              value={query}
              onChange={(event) => setQuery(event.target.value)}
              placeholder={t("palette.placeholder")}
              className="h-12 w-full bg-transparent text-sm text-[var(--foreground)] outline-none placeholder:text-muted-foreground"
              style={{ background: "transparent", border: "none", boxShadow: "none" }}
            />
            <kbd className="label-mono shrink-0 rounded border border-[var(--glass-border)] px-1.5 py-0.5">
              esc
            </kbd>
          </div>
          <div ref={listRef} className="max-h-[50vh] overflow-y-auto p-2">
            {entries.length === 0 ? (
              <p className="px-3 py-6 text-center text-sm text-muted-foreground">
                {t("palette.noResults")}
              </p>
            ) : (
              sections.map(({ key, label }) => {
                const sectionEntries = entries.filter((entry) => entry.section === key);
                if (sectionEntries.length === 0) {
                  return null;
                }
                return (
                  <div key={key} className="mb-1">
                    <p className="label-mono px-3 py-1.5">{label}</p>
                    {sectionEntries.map((entry) => {
                      const index = entries.indexOf(entry);
                      const Icon = entry.icon;
                      return (
                        <button
                          key={entry.id}
                          type="button"
                          data-active={index === activeIndex}
                          onMouseEnter={() => setActiveIndex(index)}
                          onClick={() => entry.run()}
                          className={cn(
                            "flex w-full items-center gap-2.5 rounded-md px-3 py-2 text-left text-sm",
                            index === activeIndex
                              ? "bg-[var(--accent-bg-subtle)] text-[var(--foreground)]"
                              : "text-[var(--foreground-muted)]",
                          )}
                        >
                          {Icon ? <Icon className="size-4 shrink-0" /> : null}
                          <span className="min-w-0 flex-1 truncate">{entry.label}</span>
                          {entry.hint ? (
                            <span className="shrink-0 text-xs text-muted-foreground">
                              {entry.hint}
                            </span>
                          ) : null}
                        </button>
                      );
                    })}
                  </div>
                );
              })
            )}
          </div>
        </DialogPrimitive.Content>
      </DialogPrimitive.Portal>
    </DialogPrimitive.Root>
  );
}
