/**
 * Alerts — client price-alert rules and their event feed (P3 backend live).
 * Rules CRUD works now; the trigger engine ships in the next backend slice,
 * so the events tab honestly stays empty until then.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Bell, BellRing, Plus, Trash2 } from "lucide-react";
import type { AlertRule } from "@/api/alerts";
import { CreateAlertDialog } from "@/components/alerts/CreateAlertDialog";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { ErrorState } from "@/components/ui-custom/ErrorState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/skeleton";
import { Switch } from "@/components/ui/switch";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import {
  useAlertEvents,
  useAlertRules,
  useDeleteAlertRule,
  useUpdateAlertRule,
} from "@/hooks/useAlerts";
import { formatPriceNumber, formatRelativeTime } from "@/lib/formatters";
import { safeNumber } from "@/lib/safeNumber";
import { cn } from "@/lib/utils";

const ALERT_TYPE_LABELS: Record<AlertRule["alert_type"], string> = {
  price_drop: "alerts.type.price_drop",
  price_rise: "alerts.type.price_rise",
  availability: "alerts.type.availability",
};
const CHANNEL_LABELS: Record<AlertRule["channel"], string> = {
  in_app: "alerts.channel.inApp",
  email: "alerts.channel.email",
  telegram: "alerts.channel.telegram",
  webhook: "alerts.channel.webhook",
};

function RuleRow({ rule }: { rule: AlertRule }) {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const updateRule = useUpdateAlertRule();
  const deleteRule = useDeleteAlertRule();

  return (
    <li className="flex items-center gap-3 border-b border-[var(--glass-border)] px-4 py-3 last:border-b-0">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {rule.product_title ?? t("market.overview.untitled")}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {rule.marketplace_name ?? "—"}
          {rule.last_triggered_at
            ? ` · ${t("alerts.rules.lastTriggered")}: ${formatRelativeTime(rule.last_triggered_at, locale)}`
            : null}
        </p>
      </div>
      <span className="label-mono hidden shrink-0 rounded border border-[var(--glass-border)] px-1.5 py-0.5 sm:inline">
        {t(ALERT_TYPE_LABELS[rule.alert_type])}
        {rule.threshold_pct != null ? ` ≥ ${rule.threshold_pct}%` : ""}
      </span>
      <span className="label-mono hidden shrink-0 sm:inline">
        {(rule.channels && rule.channels.length > 0 ? rule.channels : [rule.channel])
          .map((channel) => t(CHANNEL_LABELS[channel]))
          .join(" · ")}
      </span>
      <Switch
        checked={rule.is_active}
        aria-label={t(rule.is_active ? "alerts.rules.active" : "alerts.rules.paused")}
        disabled={updateRule.isPending}
        onCheckedChange={(checked) => {
          updateRule.mutate(
            { id: rule.id, is_active: checked === true },
            {
              onSuccess: () => toast.success(t("alerts.toast.updated")),
              onError: () => toast.error(t("common.error")),
            },
          );
        }}
      />
      <Button
        variant="ghost"
        size="icon"
        className="size-8 shrink-0 text-muted-foreground hover:text-[var(--status-error)]"
        aria-label={t("common.delete")}
        disabled={deleteRule.isPending}
        onClick={() => {
          deleteRule.mutate(rule.id, {
            onSuccess: () => toast.success(t("alerts.toast.deleted")),
            onError: () => toast.error(t("common.error")),
          });
        }}
      >
        <Trash2 className="size-3.5" />
      </Button>
    </li>
  );
}

export function AlertsPage() {
  const { t, i18n } = useTranslation();
  const locale = i18n.language || "en";
  const [tab, setTab] = useState<"rules" | "events">("rules");
  const [createOpen, setCreateOpen] = useState(false);

  const rulesQuery = useAlertRules();
  const eventsQuery = useAlertEvents({ limit: 50, offset: 0 });

  const rules = rulesQuery.data?.items ?? [];
  const events = eventsQuery.data?.items ?? [];

  return (
    <div className="flex h-full flex-col pb-1">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <PageHeader title="nav.alerts" />
        <Button size="sm" onClick={() => setCreateOpen(true)}>
          <Plus className="me-1.5 size-3.5" />
          {t("alerts.create.title")}
        </Button>
      </div>

      <Tabs
        value={tab}
        onValueChange={(value) => setTab(value as "rules" | "events")}
        className="mt-3 flex flex-1 flex-col"
      >
        <TabsList className="surface-base mb-3 w-fit rounded-lg p-1">
          <TabsTrigger value="rules" className="rounded-md px-3 text-xs">
            {t("alerts.tabs.rules")}
            {rules.length > 0 ? (
              <span className="ms-1.5 tabular-nums text-muted-foreground">{rules.length}</span>
            ) : null}
          </TabsTrigger>
          <TabsTrigger value="events" className="rounded-md px-3 text-xs">
            {t("alerts.tabs.events")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="mt-0 flex-1">
          <div className="surface-base overflow-hidden rounded-xl">
            {rulesQuery.isError ? (
              <ErrorState
                title="common.error"
                retry={{ label: "common.refresh", onClick: () => rulesQuery.refetch() }}
              />
            ) : rulesQuery.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : rules.length === 0 ? (
              <EmptyState
                icon={Bell}
                title="alerts.rules.empty"
                description="alerts.rules.emptyHint"
                action={{
                  label: "alerts.create.title",
                  onClick: () => setCreateOpen(true),
                }}
              />
            ) : (
              <ul>
                {rules.map((rule) => (
                  <RuleRow key={rule.id} rule={rule} />
                ))}
              </ul>
            )}
          </div>
        </TabsContent>

        <TabsContent value="events" className="mt-0 flex-1">
          <div className="surface-base overflow-hidden rounded-xl">
            {eventsQuery.isError ? (
              <ErrorState
                title="common.error"
                retry={{ label: "common.refresh", onClick: () => eventsQuery.refetch() }}
              />
            ) : eventsQuery.isLoading ? (
              <div className="space-y-2 p-4">
                {Array.from({ length: 4 }).map((_, index) => (
                  <Skeleton key={index} className="h-12 w-full" />
                ))}
              </div>
            ) : events.length === 0 ? (
              <EmptyState
                icon={BellRing}
                title="alerts.events.empty"
                description="alerts.events.emptyHint"
              />
            ) : (
              <ul>
                {events.map((event) => {
                  const change = event.change_pct == null ? null : safeNumber(event.change_pct);
                  return (
                    <li
                      key={event.id}
                      className="flex items-center gap-3 border-b border-[var(--glass-border)] px-4 py-3 last:border-b-0"
                    >
                      <div className="min-w-0 flex-1">
                        <p className="truncate text-sm font-medium">
                          {event.product_title ?? t("market.overview.untitled")}
                        </p>
                        <p className="truncate text-xs text-muted-foreground">
                          {event.marketplace_name ?? "—"} ·{" "}
                          {formatRelativeTime(event.triggered_at, locale)}
                        </p>
                      </div>
                      <p className="shrink-0 font-mono text-sm tabular-nums">
                        {event.old_price != null ? (
                          <span className="text-muted-foreground">
                            {formatPriceNumber(safeNumber(event.old_price), locale)} →{" "}
                          </span>
                        ) : null}
                        {event.new_price != null
                          ? formatPriceNumber(safeNumber(event.new_price), locale)
                          : "—"}{" "}
                        {event.currency ?? ""}
                      </p>
                      {change != null ? (
                        <span
                          className={cn(
                            "shrink-0 font-mono text-xs font-medium tabular-nums",
                            change > 0
                              ? "text-[var(--color-price-up)]"
                              : "text-[var(--color-price-down)]",
                          )}
                        >
                          {change > 0 ? "+" : ""}
                          {change.toFixed(2)}%
                        </span>
                      ) : null}
                    </li>
                  );
                })}
              </ul>
            )}
          </div>
        </TabsContent>
      </Tabs>

      <CreateAlertDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
