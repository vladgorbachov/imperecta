import { useMemo, useState } from "react";
import { CheckCircle2 } from "lucide-react";
import { useTranslation } from "react-i18next";
import type { ServiceAlertResolvedFilter, ServiceAlertSeverity } from "@/api/admin";
import { ServiceAlertRow } from "@/components/admin/alerts/ServiceAlertRow";
import { isServiceAlertSeverity } from "@/components/admin/alerts/alertSeverity";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { Skeleton } from "@/components/ui/skeleton";
import { useServiceAlerts } from "@/hooks/useAdmin";
import { cn } from "@/lib/utils";

const PAGE_LIMIT = 50;

/** Static discovery submodules (documented set); other modules derive
    submodule filter options from the loaded rows. */
const DISCOVERY_SUBMODULES = [
  "fetch_adapter",
  "url_canonicalizer",
  "classifier_adapter",
  "budget_governor",
] as const;

/** Every module now has real server-side emitters (backend 2026-09-16). */
const MODULES = [
  { id: "discovery", labelKey: "admin.alerts.module.discovery" },
  { id: "scraper", labelKey: "admin.alerts.module.scraper" },
  { id: "parser", labelKey: "admin.alerts.module.parser" },
  { id: "quality", labelKey: "admin.alerts.module.quality" },
  { id: "market_data", labelKey: "admin.alerts.module.marketData" },
  { id: "data_firewall", labelKey: "admin.alerts.module.dataFirewall" },
] as const;

type ModuleId = (typeof MODULES)[number]["id"];

const SEVERITY_OPTIONS: ServiceAlertSeverity[] = ["critical", "error", "warning", "info"];

const RESOLVED_FILTERS: ServiceAlertResolvedFilter[] = ["open", "resolved", "all"];

const RESOLVED_LABEL_KEYS: Record<ServiceAlertResolvedFilter, string> = {
  open: "admin.alerts.open",
  resolved: "admin.alerts.resolved",
  all: "admin.alerts.all",
};

const SEVERITY_LABEL_KEYS: Record<ServiceAlertSeverity, string> = {
  info: "admin.alerts.severity.info",
  warning: "admin.alerts.severity.warning",
  error: "admin.alerts.severity.error",
  critical: "admin.alerts.severity.critical",
};

function countBySeverity(
  items: Array<{ severity: string }>,
): Record<ServiceAlertSeverity, number> {
  const counts: Record<ServiceAlertSeverity, number> = {
    info: 0,
    warning: 0,
    error: 0,
    critical: 0,
  };
  for (const item of items) {
    if (isServiceAlertSeverity(item.severity)) {
      counts[item.severity] += 1;
    }
  }
  return counts;
}

/** Sidebar entry with its own open-count badge (one cheap limit-1 query each). */
function ModuleButton({
  module,
  active,
  onSelect,
}: {
  module: (typeof MODULES)[number];
  active: boolean;
  onSelect: (id: ModuleId) => void;
}) {
  const { t } = useTranslation();
  const openCount = useServiceAlerts({
    module: module.id,
    resolved: "open",
    limit: 1,
    offset: 0,
  });
  const count = openCount.data?.total ?? 0;

  return (
    <button
      type="button"
      onClick={() => onSelect(module.id)}
      className={cn(
        "flex w-full items-center justify-between rounded-md border px-3 py-2 text-left text-sm transition-colors",
        active
          ? "border-[var(--accent-border)] bg-[var(--accent-bg)] text-foreground"
          : "border-border/60 text-muted-foreground hover:bg-[var(--glass-bg-hover)] hover:text-foreground",
      )}
    >
      <span>{t(module.labelKey)}</span>
      {count > 0 ? (
        <Badge variant="outline" className="text-2xs">
          {count}
        </Badge>
      ) : null}
    </button>
  );
}

export function AlertsTab() {
  const { t } = useTranslation();
  const [selectedModule, setSelectedModule] = useState<ModuleId>("discovery");
  const [resolved, setResolved] = useState<ServiceAlertResolvedFilter>("open");
  const [severityFilter, setSeverityFilter] = useState<string>("all");
  const [submoduleFilter, setSubmoduleFilter] = useState<string>("all");
  const [offset, setOffset] = useState(0);

  const listParams = useMemo(
    () => ({
      module: selectedModule,
      resolved,
      limit: PAGE_LIMIT,
      offset,
      ...(severityFilter !== "all" ? { severity: severityFilter } : {}),
      ...(submoduleFilter !== "all" ? { submodule: submoduleFilter } : {}),
    }),
    [selectedModule, resolved, severityFilter, submoduleFilter, offset],
  );

  const { data, isLoading, isError, isFetching } = useServiceAlerts(listParams);

  const openCountQuery = useServiceAlerts({
    module: selectedModule,
    resolved: "open",
    limit: 1,
    offset: 0,
  });

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const openTotal = openCountQuery.data?.total ?? 0;
  const severityCounts = useMemo(() => countBySeverity(items), [items]);
  const countsPartial = total > items.length;

  /* Submodule filter options: static for discovery, derived from rows elsewhere. */
  const submoduleOptions = useMemo(() => {
    if (selectedModule === "discovery") {
      return [...DISCOVERY_SUBMODULES];
    }
    return [...new Set(items.map((item) => item.submodule))].sort();
  }, [selectedModule, items]);

  const handleModuleSelect = (id: ModuleId) => {
    setSelectedModule(id);
    setSubmoduleFilter("all");
    setSeverityFilter("all");
    setOffset(0);
  };

  const hasMore = offset + PAGE_LIMIT < total;
  const hasPrev = offset > 0;

  const handleResolvedChange = (next: ServiceAlertResolvedFilter) => {
    setResolved(next);
    setOffset(0);
  };

  const handleSeverityChange = (value: string) => {
    setSeverityFilter(value);
    setOffset(0);
  };

  const handleSubmoduleChange = (value: string) => {
    setSubmoduleFilter(value);
    setOffset(0);
  };

  return (
    <div className="grid gap-4 lg:grid-cols-[220px_minmax(0,1fr)]">
      <Card className="h-fit lg:sticky lg:top-2">
        <CardHeader className="pb-3">
          <CardTitle className="text-sm">{t("admin.alerts.modules")}</CardTitle>
        </CardHeader>
        <CardContent className="space-y-1 p-3 pt-0">
          {MODULES.map((module) => (
            <ModuleButton
              key={module.id}
              module={module}
              active={selectedModule === module.id}
              onSelect={handleModuleSelect}
            />
          ))}
        </CardContent>
      </Card>

      <div className="space-y-4">
        <Card>
          <CardHeader className="pb-3">
            <CardTitle>{t("admin.alerts.title")}</CardTitle>
            <CardDescription>{t("admin.alerts.subtitle")}</CardDescription>
          </CardHeader>
          <CardContent className="grid grid-cols-2 gap-2 sm:grid-cols-4">
            <div className="rounded-md border border-border/60 p-3">
              <p className="text-2xs text-muted-foreground">{t("admin.alerts.open")}</p>
              <p className="text-xl font-semibold tabular-nums">
                {resolved === "open" ? total : openTotal}
              </p>
            </div>
            {SEVERITY_OPTIONS.map((severity) => (
              <div key={severity} className="rounded-md border border-border/60 p-3">
                <p className="text-2xs text-muted-foreground">
                  {t(SEVERITY_LABEL_KEYS[severity])}
                </p>
                <p className="text-xl font-semibold tabular-nums">
                  {severityCounts[severity]}
                </p>
              </div>
            ))}
            {countsPartial ? (
              <p className="col-span-full text-2xs text-muted-foreground">
                {t("admin.alerts.severityCountsHint")}
              </p>
            ) : null}
          </CardContent>
        </Card>

        <Card>
          <CardHeader className="space-y-3 pb-3">
            <div className="flex flex-wrap items-center gap-2">
              <div className="flex rounded-md border border-border/60 p-0.5">
                {RESOLVED_FILTERS.map((filter) => (
                  <Button
                    key={filter}
                    type="button"
                    size="sm"
                    variant="ghost"
                    className={cn(
                      "h-7 px-2.5 text-xs",
                      resolved === filter && "bg-muted font-medium",
                    )}
                    onClick={() => handleResolvedChange(filter)}
                  >
                    {t(RESOLVED_LABEL_KEYS[filter])}
                  </Button>
                ))}
              </div>

              <Select value={severityFilter} onValueChange={handleSeverityChange}>
                <SelectTrigger className="h-8 w-[140px] text-xs">
                  <SelectValue placeholder={t("admin.alerts.severityFilter")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("admin.alerts.allSeverities")}</SelectItem>
                  {SEVERITY_OPTIONS.map((severity) => (
                    <SelectItem key={severity} value={severity}>
                      {t(SEVERITY_LABEL_KEYS[severity])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              <Select value={submoduleFilter} onValueChange={handleSubmoduleChange}>
                <SelectTrigger className="h-8 w-[180px] text-xs">
                  <SelectValue placeholder={t("admin.alerts.submoduleFilter")} />
                </SelectTrigger>
                <SelectContent>
                  <SelectItem value="all">{t("admin.alerts.allSubmodules")}</SelectItem>
                  {submoduleOptions.map((submodule) => (
                    <SelectItem key={submodule} value={submodule}>
                      {submodule}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>

              {isFetching && !isLoading ? (
                <span className="text-2xs text-muted-foreground">{t("admin.alerts.refreshing")}</span>
              ) : null}
            </div>
          </CardHeader>

          <CardContent className="space-y-2">
            {isLoading ? (
              <div className="space-y-2" data-testid="alerts-skeleton">
                {Array.from({ length: 4 }, (_, index) => (
                  <Skeleton key={index} className="h-16 w-full" />
                ))}
              </div>
            ) : isError ? (
              <p className="text-sm text-muted-foreground">{t("admin.alerts.loadError")}</p>
            ) : items.length === 0 ? (
              <EmptyState
                title="admin.alerts.empty"
                description="admin.alerts.emptyHint"
                icon={CheckCircle2}
                className="py-10"
              />
            ) : (
              <div className="space-y-2">
                {items.map((alert) => (
                  <ServiceAlertRow key={alert.id} alert={alert} />
                ))}
              </div>
            )}

            {total > PAGE_LIMIT ? (
              <div className="flex items-center justify-between pt-2">
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!hasPrev}
                  onClick={() => setOffset((value) => Math.max(0, value - PAGE_LIMIT))}
                >
                  {t("common.back")}
                </Button>
                <span className="text-2xs text-muted-foreground">
                  {offset + 1}–{Math.min(offset + PAGE_LIMIT, total)} / {total}
                </span>
                <Button
                  type="button"
                  variant="outline"
                  size="sm"
                  disabled={!hasMore}
                  onClick={() => setOffset((value) => value + PAGE_LIMIT)}
                >
                  {t("common.next")}
                </Button>
              </div>
            ) : null}
          </CardContent>
        </Card>
      </div>
    </div>
  );
}
