/**
 * Append-only audit log of the blocked-countries list: cursor-paged, each
 * entry expands to its before/after snapshot so a reviewer can see exactly
 * what changed and who did it.
 */

import { useEffect, useState } from "react";
import { useTranslation } from "react-i18next";
import { ChevronDown } from "lucide-react";
import type { BlockedCountryAudit, BlockedCountryAuditAction } from "@/api/admin";
import { useBlockedCountriesAudit } from "@/hooks/useAdmin";
import { Button } from "@/components/ui/button";
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from "@/components/ui/collapsible";
import { Sheet, SheetContent, SheetHeader, SheetTitle } from "@/components/ui/sheet";
import { Skeleton } from "@/components/ui/skeleton";
import { flagForCode } from "@/lib/countryFlag";
import { formatDateTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";

const ACTION_LABELS: Record<BlockedCountryAuditAction, string> = {
  add: "admin.compliance.audit.action.add",
  remove: "admin.compliance.audit.action.remove",
  edit: "admin.compliance.audit.action.edit",
  review: "admin.compliance.audit.action.review",
};

const ACTION_CLASS: Record<BlockedCountryAuditAction, string> = {
  add: "!text-[var(--status-error)]",
  remove: "!text-[var(--status-ok)]",
  edit: "!text-[var(--accent)]",
  review: "!text-[var(--status-warn)]",
};

function Snapshot({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="min-w-0">
      <p className="label-mono mb-1">{label}</p>
      <pre className="max-h-48 overflow-auto rounded-md border border-[var(--glass-border)] bg-[var(--surface-sunken-bg)] p-2 font-mono text-2xs leading-relaxed">
        {value == null ? "—" : JSON.stringify(value, null, 2)}
      </pre>
    </div>
  );
}

function AuditRow({ entry, locale }: { entry: BlockedCountryAudit; locale: string }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  return (
    <Collapsible open={open} onOpenChange={setOpen} asChild>
      <li className="border-b border-[var(--glass-border)] py-2 last:border-b-0">
        <CollapsibleTrigger asChild>
          <button
            type="button"
            className="flex w-full items-center gap-2 text-left"
            aria-expanded={open}
          >
            <span className={cn("label-mono w-16 shrink-0", ACTION_CLASS[entry.action])}>
              {t(ACTION_LABELS[entry.action])}
            </span>
            <span aria-hidden>{flagForCode(entry.country_code)}</span>
            <span className="font-mono text-xs">{entry.country_code}</span>
            <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground">
              {entry.actor?.email ?? t("admin.compliance.audit.system")} ·{" "}
              {formatDateTime(entry.at, locale)}
            </span>
            <ChevronDown
              className={cn("size-3.5 shrink-0 transition-transform", open && "rotate-180")}
            />
          </button>
        </CollapsibleTrigger>
        <CollapsibleContent>
          <div className="mt-2 space-y-2">
            {entry.note ? <p className="text-xs">{entry.note}</p> : null}
            <div className="grid gap-2 sm:grid-cols-2">
              <Snapshot label={t("admin.compliance.audit.before")} value={entry.before} />
              <Snapshot label={t("admin.compliance.audit.after")} value={entry.after} />
            </div>
          </div>
        </CollapsibleContent>
      </li>
    </Collapsible>
  );
}

export interface BlockedCountryAuditDrawerProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function BlockedCountryAuditDrawer({ open, onOpenChange }: BlockedCountryAuditDrawerProps) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const [cursor, setCursor] = useState<string | null>(null);
  const [entries, setEntries] = useState<BlockedCountryAudit[]>([]);

  const { data, isLoading, isError, isFetching } = useBlockedCountriesAudit(cursor, open);

  /* Accumulate pages; the list resets when the drawer is reopened. */
  useEffect(() => {
    if (!data) {
      return;
    }
    setEntries((prev) => {
      const seen = new Set(prev.map((entry) => entry.id));
      const fresh = data.items.filter((entry) => !seen.has(entry.id));
      return cursor == null ? data.items : [...prev, ...fresh];
    });
  }, [data, cursor]);

  useEffect(() => {
    if (!open) {
      setCursor(null);
      setEntries([]);
    }
  }, [open]);

  return (
    <Sheet open={open} onOpenChange={onOpenChange}>
      <SheetContent
        side="right"
        className="w-full max-w-full overflow-y-auto border-s border-[var(--glass-border)] bg-[var(--background-surface)] sm:max-w-lg"
        data-testid="blocked-countries-audit"
      >
        <SheetHeader>
          <SheetTitle>{t("admin.compliance.audit.title")}</SheetTitle>
          <p className="text-xs text-muted-foreground">{t("admin.compliance.audit.subtitle")}</p>
        </SheetHeader>
        <div className="mt-4">
          {isLoading && entries.length === 0 ? (
            <div className="space-y-2">
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
              <Skeleton className="h-8 w-full" />
            </div>
          ) : isError ? (
            <p className="text-sm text-muted-foreground">{t("common.error")}</p>
          ) : entries.length === 0 ? (
            <p className="text-sm text-muted-foreground">{t("admin.compliance.audit.empty")}</p>
          ) : (
            <ul>
              {entries.map((entry) => (
                <AuditRow key={entry.id} entry={entry} locale={locale} />
              ))}
            </ul>
          )}
          {data?.next_cursor ? (
            <Button
              variant="outline"
              size="sm"
              className="mt-3 w-full"
              disabled={isFetching}
              onClick={() => setCursor(data.next_cursor)}
            >
              {t("admin.compliance.audit.loadMore")}
            </Button>
          ) : null}
        </div>
      </SheetContent>
    </Sheet>
  );
}
