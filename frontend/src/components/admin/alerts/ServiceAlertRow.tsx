import { useState } from "react";
import { ChevronDown } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ServiceAlert } from "@/api/admin";
import { Badge } from "@/components/ui/badge";
import { formatDateTime, formatRelativeTime } from "@/lib/formatters";
import { cn } from "@/lib/utils";
import { isServiceAlertSeverity, SEVERITY_STYLES } from "./alertSeverity";

export interface ServiceAlertRowProps {
  alert: ServiceAlert;
}

function formatContextValue(value: unknown): string {
  if (value == null) {
    return "—";
  }
  if (typeof value === "object") {
    return JSON.stringify(value);
  }
  return String(value);
}

export function ServiceAlertRow({ alert }: ServiceAlertRowProps) {
  const { t, i18n } = useTranslation();
  const [expanded, setExpanded] = useState(false);
  const locale = i18n.language || "en";
  const severity = isServiceAlertSeverity(alert.severity) ? alert.severity : "info";
  const styles = SEVERITY_STYLES[severity];
  const triggeredLabel = formatDateTime(alert.triggered_at, locale);
  const relativeTriggered = formatRelativeTime(alert.triggered_at, locale);

  return (
    <article
      className={cn(
        "border border-border/60 border-l-[3px] bg-[var(--glass-bg)]",
        styles.borderClass,
      )}
    >
      <button
        type="button"
        className="flex w-full items-start gap-3 px-3 py-2.5 text-left hover:bg-[var(--glass-bg-hover)]"
        onClick={() => setExpanded((value) => !value)}
        aria-expanded={expanded}
      >
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <Badge variant="outline" className={cn("text-2xs uppercase", styles.badgeClass)}>
              {t(styles.labelKey)}
            </Badge>
            <span className="font-mono text-2xs text-muted-foreground">
              {alert.module} → {alert.submodule} · {alert.anomaly_type}
            </span>
            <span
              className="ms-auto shrink-0 text-2xs text-muted-foreground"
              title={triggeredLabel}
            >
              {relativeTriggered}
            </span>
          </div>
          <p className="text-sm leading-snug text-foreground">{alert.message}</p>
        </div>
        <ChevronDown
          className={cn(
            "mt-0.5 size-4 shrink-0 text-muted-foreground transition-transform",
            expanded && "rotate-180",
          )}
          aria-hidden
        />
      </button>

      {expanded ? (
        <div className="space-y-3 border-t border-border/60 px-3 py-3 text-xs">
          <div className="grid gap-2 sm:grid-cols-2">
            <div>
              <p className="text-2xs uppercase tracking-wide text-muted-foreground">
                {t("admin.alerts.triggeredAt")}
              </p>
              <p className="font-mono">{triggeredLabel}</p>
            </div>
            {alert.resolved_at ? (
              <div>
                <p className="text-2xs uppercase tracking-wide text-muted-foreground">
                  {t("admin.alerts.resolvedAt")}
                </p>
                <p className="font-mono">{formatDateTime(alert.resolved_at, locale)}</p>
              </div>
            ) : null}
          </div>

          {alert.context && Object.keys(alert.context).length > 0 ? (
            <div>
              <p className="mb-1.5 text-2xs uppercase tracking-wide text-muted-foreground">
                {t("admin.alerts.context")}
              </p>
              <dl className="space-y-1 rounded-md border border-border/60 bg-[var(--background-elevated)] p-2 font-mono text-2xs">
                {Object.entries(alert.context).map(([key, value]) => (
                  <div key={key} className="grid grid-cols-[minmax(0,8rem)_1fr] gap-2">
                    <dt className="truncate text-muted-foreground">{key}</dt>
                    <dd className="break-all text-foreground">{formatContextValue(value)}</dd>
                  </div>
                ))}
              </dl>
            </div>
          ) : (
            <p className="text-muted-foreground">{t("admin.alerts.noContext")}</p>
          )}
        </div>
      ) : null}
    </article>
  );
}
