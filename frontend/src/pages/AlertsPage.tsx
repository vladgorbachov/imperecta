/**
 * Alerts page: Twitter-style timeline feed + sidebar.
 * i18n: nav.alerts, alerts.*, common.*
 */

import { useState, useRef, useEffect } from "react";
import { useNavigate } from "react-router-dom";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Pencil,
  Trash2,
  Mail,
  MessageCircle,
  TrendingDown,
  TrendingUp,
  PackageX,
  Tag,
} from "lucide-react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  ResponsiveContainer,
  Tooltip,
} from "recharts";
import { formatRelativeTime } from "@/lib/formatters";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "@/api/alerts";
import { productsApi } from "@/api/products";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogFooter,
} from "@/components/ui/dialog";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { RadioGroup, RadioGroupItemStyled } from "@/components/ui/radio-group";
import { Switch } from "@/components/ui/switch";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { Alert, AlertEvent } from "@/api/alerts";

type AlertType = "price_drop" | "price_increase" | "out_of_stock" | "new_promo";
type AlertChannel = "email" | "telegram" | "both";
type Priority = "critical" | "important" | "info";

const ALERT_TYPE_KEYS: Record<AlertType, string> = {
  price_drop: "alerts.typePriceDrop",
  price_increase: "alerts.typePriceIncrease",
  out_of_stock: "alerts.typeOutOfStock",
  new_promo: "alerts.typeNewPromo",
};

const ALERT_TYPE_ICONS: Record<AlertType, typeof TrendingDown> = {
  price_drop: TrendingDown,
  price_increase: TrendingUp,
  out_of_stock: PackageX,
  new_promo: Tag,
};

const PRIORITY_STRIPE: Record<Priority, string> = {
  critical: "border-l-red-500 dark:border-l-red-500",
  important: "border-l-orange-500 dark:border-l-orange-500",
  info: "border-l-blue-500 dark:border-l-blue-500",
};

function getEventType(ev: AlertEvent): AlertType {
  if (ev.old_price != null && ev.new_price != null) {
    return ev.new_price < ev.old_price ? "price_drop" : "price_increase";
  }
  if (ev.message?.toLowerCase().includes("promo")) return "new_promo";
  return "out_of_stock";
}

function getEventPriority(ev: AlertEvent, type: AlertType): Priority {
  if (type === "out_of_stock") return "critical";
  if (type === "price_drop" && ev.old_price != null && ev.new_price != null) {
    const pct = ((ev.old_price - ev.new_price) / ev.old_price) * 100;
    return pct >= 15 ? "critical" : "important";
  }
  if (type === "price_increase") return "important";
  return "info";
}

function groupEventsByDay(events: AlertEvent[]): Array<{ day: string; count: number }> {
  const dayNames = ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"];
  const counts: Record<string, number> = {};
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    counts[key] = 0;
  }
  for (const ev of events) {
    const key = ev.triggered_at?.slice(0, 10) ?? "";
    if (key in counts) counts[key]++;
  }
  const result: Array<{ day: string; count: number }> = [];
  for (let i = 6; i >= 0; i--) {
    const d = new Date();
    d.setDate(d.getDate() - i);
    const key = d.toISOString().slice(0, 10);
    const dayName = dayNames[d.getDay() === 0 ? 6 : d.getDay() - 1];
    result.push({ day: dayName, count: counts[key] ?? 0 });
  }
  return result;
}

interface SearchableProductSelectProps {
  value: string;
  onChange: (value: string) => void;
  products: { id: string; name: string; sku: string | null }[];
  placeholder?: string;
}

function SearchableProductSelect({
  value,
  onChange,
  products,
  placeholder,
}: SearchableProductSelectProps) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [search, setSearch] = useState("");
  const ref = useRef<HTMLDivElement>(null);

  const filtered = products.filter(
    (p) =>
      p.name.toLowerCase().includes(search.toLowerCase()) ||
      (p.sku?.toLowerCase().includes(search.toLowerCase()) ?? false)
  );
  const selectedProduct = products.find((p) => p.id === value);

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (ref.current && !ref.current.contains(e.target as Node)) setOpen(false);
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <div ref={ref} className="relative">
      <div
        className="flex h-10 w-full cursor-pointer items-center justify-between rounded-md border border-input bg-background px-3 py-2 text-sm ring-offset-background focus-within:ring-2 focus-within:ring-ring focus-within:ring-offset-2"
        onClick={() => setOpen(!open)}
      >
        <span className={selectedProduct ? "" : "text-muted-foreground"}>
          {selectedProduct
            ? `${selectedProduct.name}${selectedProduct.sku ? ` (${selectedProduct.sku})` : ""}`
            : placeholder ?? t("alerts.allProducts")}
        </span>
      </div>
      {open && (
        <div className="absolute top-full left-0 right-0 z-50 mt-1 max-h-60 overflow-hidden rounded-md border border-border bg-popover shadow-md dark:border-border dark:bg-popover">
          <Input
            placeholder={t("products.search")}
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="m-2 h-8"
            autoFocus
          />
          <div className="max-h-44 overflow-y-auto p-1">
            <button
              type="button"
              className="flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
              onClick={() => {
                onChange("");
                setOpen(false);
                setSearch("");
              }}
            >
              {t("alerts.allProducts")}
            </button>
            {filtered.map((p) => (
              <button
                key={p.id}
                type="button"
                className="flex w-full cursor-pointer items-center rounded-sm px-2 py-1.5 text-left text-sm hover:bg-accent hover:text-accent-foreground"
                onClick={() => {
                  onChange(p.id);
                  setOpen(false);
                  setSearch("");
                }}
              >
                {p.name}
                {p.sku && (
                  <span className="ml-2 text-muted-foreground">({p.sku})</span>
                )}
              </button>
            ))}
            {filtered.length === 0 && (
              <p className="px-2 py-4 text-center text-sm text-muted-foreground">
                {t("products.noResults")}
              </p>
            )}
          </div>
        </div>
      )}
    </div>
  );
}

export function AlertsPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const locale = i18n.language;
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [, setEditAlert] = useState<Alert | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [form, setForm] = useState({
    product_id: "",
    type: "price_drop" as AlertType,
    threshold_percent: "",
    channel: "email" as AlertChannel,
  });
  const [typeFilter, setTypeFilter] = useState<string>("all");
  const [priorityFilter, setPriorityFilter] = useState<string>("all");
  const [channelFilter, setChannelFilter] = useState<string>("all");

  const { data: alertsResponse } = useQuery({
    queryKey: ["alerts"],
    queryFn: () => alertsApi.list(),
  });
  const alerts = alertsResponse?.data ?? [];

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["alerts", "events"],
    queryFn: async () => {
      const { data } = await alertsApi.getEvents(50);
      return data;
    },
  });

  const { data: productsData } = useQuery({
    queryKey: ["products"],
    queryFn: async () => {
      const { data } = await productsApi.list({ limit: 500 });
      return data;
    },
  });
  const products = productsData?.items ?? [];

  const alertById = Object.fromEntries(alerts.map((a) => [a.id, a]));

  const filteredEvents = events.filter((ev) => {
    const type = getEventType(ev);
    const priority = getEventPriority(ev, type);
    const typeMatch =
      typeFilter === "all" ||
      (typeFilter === "price" && (type === "price_drop" || type === "price_increase")) ||
      (typeFilter === "stock" && type === "out_of_stock") ||
      (typeFilter === "promo" && type === "new_promo");
    const priorityMatch =
      priorityFilter === "all" || priorityFilter === priority;
    const channelMatch =
      channelFilter === "all" ||
      (channelFilter === "email" && ev.sent_via?.toLowerCase().includes("email")) ||
      (channelFilter === "telegram" && ev.sent_via?.toLowerCase().includes("telegram"));
    return typeMatch && priorityMatch && channelMatch;
  });

  const alertsByDayData = groupEventsByDay(events);
  const today = new Date().toISOString().slice(0, 10);
  const alertsTodayCount = events.filter((e) => e.triggered_at?.slice(0, 10) === today).length;

  const createMutation = useMutation({
    mutationFn: alertsApi.create,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setCreateOpen(false);
      setEditAlert(null);
      setForm({ product_id: "", type: "price_drop", threshold_percent: "", channel: "email" });
      toast.success(t("alerts.createSuccess"));
    },
    onError: () => toast.error(t("alerts.createError")),
  });

  const updateMutation = useMutation({
    mutationFn: ({ id, is_active }: { id: string; is_active: boolean }) =>
      alertsApi.update(id, { is_active }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["alerts"] }),
  });

  const deleteMutation = useMutation({
    mutationFn: alertsApi.delete,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["alerts"] });
      setDeleteConfirmId(null);
      toast.success(t("common.delete"));
    },
  });

  const handleCreate = (e: React.FormEvent) => {
    e.preventDefault();
    createMutation.mutate({
      product_id: form.product_id || undefined,
      type: form.type,
      threshold_percent: form.threshold_percent ? parseFloat(form.threshold_percent) : undefined,
      channel: form.channel,
    });
  };

  const openEdit = (alert: Alert) => {
    setEditAlert(alert);
    setForm({
      product_id: alert.product_id ?? "",
      type: alert.type as AlertType,
      threshold_percent: alert.threshold_percent?.toString() ?? "",
      channel: alert.channel as AlertChannel,
    });
    setCreateOpen(true);
  };

  const showThreshold = form.type === "price_drop" || form.type === "price_increase";

  const handleAutoResponse = (_ev: AlertEvent) => {
    toast.info(t("alerts.autoResponseSuggested"));
    // TODO: POST /api/ai/auto-response
  };

  return (
    <div className="space-y-6">
      <PageHeader title="nav.alerts" />

      <div className="flex flex-col gap-6 lg:flex-row">
        {/* Left: Timeline feed (70%) */}
        <div className="min-w-0 flex-1 lg:max-w-[70%]">
          <div className="mb-4 grid grid-cols-2 gap-2 sm:flex sm:flex-wrap">
            <Select value={typeFilter} onValueChange={setTypeFilter}>
              <SelectTrigger className="w-full min-w-0 sm:w-36">
                <SelectValue placeholder={t("alerts.filterType")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("alerts.filterAll")}</SelectItem>
                <SelectItem value="price">{t("alerts.filterPrice")}</SelectItem>
                <SelectItem value="stock">{t("alerts.filterStock")}</SelectItem>
                <SelectItem value="promo">{t("alerts.filterPromo")}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={priorityFilter} onValueChange={setPriorityFilter}>
              <SelectTrigger className="w-full min-w-0 sm:w-36">
                <SelectValue placeholder={t("alerts.filterPriority")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("alerts.filterAll")}</SelectItem>
                <SelectItem value="critical">{t("alerts.priorityCritical")}</SelectItem>
                <SelectItem value="important">{t("alerts.priorityImportant")}</SelectItem>
                <SelectItem value="info">{t("alerts.priorityInfo")}</SelectItem>
              </SelectContent>
            </Select>
            <Select value={channelFilter} onValueChange={setChannelFilter}>
              <SelectTrigger className="w-full min-w-0 sm:w-36">
                <SelectValue placeholder={t("alerts.filterChannel")} />
              </SelectTrigger>
              <SelectContent>
                <SelectItem value="all">{t("alerts.filterAll")}</SelectItem>
                <SelectItem value="email">{t("alerts.channelEmail")}</SelectItem>
                <SelectItem value="telegram">{t("alerts.channelTelegram")}</SelectItem>
              </SelectContent>
            </Select>
          </div>

          {eventsLoading ? (
            <div className="space-y-4">
              {Array.from({ length: 5 }).map((_, i) => (
                <div key={i} className="h-40 animate-pulse rounded-lg border bg-muted" />
              ))}
            </div>
          ) : filteredEvents.length === 0 ? (
            <EmptyState
              title="alerts.eventHistoryEmpty"
              description="alerts.eventHistoryEmptyHint"
              icon={PackageX}
            />
          ) : (
            <div className="space-y-4">
              {filteredEvents.map((ev) => (
                <TimelineCard
                  key={ev.id}
                  event={ev}
                  locale={locale}
                  productId={alertById[ev.alert_id]?.product_id ?? null}
                  onAutoResponse={() => handleAutoResponse(ev)}
                  onViewProduct={() => {
                    const pid = alertById[ev.alert_id]?.product_id;
                    if (pid) navigate(`/products/${pid}`);
                  }}
                />
              ))}
            </div>
          )}
        </div>

        {/* Right: Sidebar (30%) */}
        <aside className="w-full space-y-6 lg:w-[30%] lg:min-w-[280px]">
          <div className="rounded-xl border border-border bg-card p-4 shadow-sm dark:border-border">
            <h3 className="mb-3 text-sm font-semibold">{t("alerts.alertsToday")}</h3>
            <p className="mb-4 text-3xl font-bold">{alertsTodayCount}</p>
            <div className="h-24">
              <ResponsiveContainer width="100%" height="100%">
                <BarChart data={alertsByDayData} margin={{ top: 4, right: 4, left: 0, bottom: 0 }}>
                  <XAxis dataKey="day" tick={{ fontSize: 10 }} stroke="hsl(var(--muted-foreground))" />
                  <YAxis hide />
                  <Tooltip
                    content={({ active, payload }) => {
                      if (!active || !payload?.length) return null;
                      const p = payload[0]?.payload;
                      return (
                        <div className="rounded-md border border-border bg-card px-2 py-1 text-xs">
                          {p?.day}: {p?.count} {t("alerts.alerts")}
                        </div>
                      );
                    }}
                  />
                  <Bar dataKey="count" fill="hsl(var(--primary))" radius={[2, 2, 0, 0]} />
                </BarChart>
              </ResponsiveContainer>
            </div>
          </div>

          <div className="rounded-xl border border-border bg-card p-4 shadow-sm dark:border-border">
            <div className="mb-3 flex items-center justify-between">
              <h3 className="text-sm font-semibold">{t("alerts.activeRules")}</h3>
              <Button size="sm" onClick={() => { setEditAlert(null); setForm({ product_id: "", type: "price_drop", threshold_percent: "", channel: "email" }); setCreateOpen(true); }}>
                <Plus className="mr-2 size-4" />
                {t("alerts.createRule")}
              </Button>
            </div>
            <div className="space-y-2">
              {alerts.length === 0 ? (
                <p className="py-4 text-center text-sm text-muted-foreground">
                  {t("alerts.noAlerts")}
                </p>
              ) : (
                alerts.map((a) => (
                  <AlertRuleCompact
                    key={a.id}
                    alert={a}
                    onToggle={(enabled) => updateMutation.mutate({ id: a.id, is_active: enabled })}
                    onEdit={() => openEdit(a)}
                    onDelete={() => setDeleteConfirmId(a.id)}
                  />
                ))
              )}
            </div>
          </div>
        </aside>
      </div>

      {/* Create/Edit dialog */}
      <Dialog
        open={createOpen}
        onOpenChange={(open) => {
          setCreateOpen(open);
          if (!open) setEditAlert(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("alerts.createAlert")}</DialogTitle>
          </DialogHeader>
          <form onSubmit={handleCreate}>
            <div className="space-y-4 py-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("alerts.product")}</label>
                <SearchableProductSelect
                  value={form.product_id}
                  onChange={(v) => setForm((f) => ({ ...f, product_id: v }))}
                  products={products}
                  placeholder={t("alerts.allProducts")}
                />
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("alerts.type")}</label>
                <Select
                  value={form.type}
                  onValueChange={(v) => setForm((f) => ({ ...f, type: v as AlertType }))}
                >
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {(Object.keys(ALERT_TYPE_KEYS) as AlertType[]).map((typeKey) => (
                      <SelectItem key={typeKey} value={typeKey}>
                        {t(ALERT_TYPE_KEYS[typeKey])}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              {showThreshold && (
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("alerts.threshold")} %</label>
                  <Input
                    type="number"
                    step="0.1"
                    min="0"
                    max="100"
                    value={form.threshold_percent}
                    onChange={(e) => setForm((f) => ({ ...f, threshold_percent: e.target.value }))}
                    placeholder={t("alerts.thresholdPlaceholder")}
                  />
                </div>
              )}
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("alerts.channel")}</label>
                <RadioGroup
                  value={form.channel}
                  onValueChange={(v) => setForm((f) => ({ ...f, channel: v as AlertChannel }))}
                  className="flex flex-col gap-2"
                >
                  <div className="flex items-center gap-2">
                    <RadioGroupItemStyled value="email" id="channel-email" />
                    <label htmlFor="channel-email" className="cursor-pointer text-sm">
                      {t("alerts.channelEmail")}
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <RadioGroupItemStyled value="telegram" id="channel-telegram" />
                    <label htmlFor="channel-telegram" className="cursor-pointer text-sm">
                      {t("alerts.channelTelegram")}
                    </label>
                  </div>
                  <div className="flex items-center gap-2">
                    <RadioGroupItemStyled value="both" id="channel-both" />
                    <label htmlFor="channel-both" className="cursor-pointer text-sm">
                      {t("alerts.channelBoth")}
                    </label>
                  </div>
                </RadioGroup>
              </div>
            </div>
            <DialogFooter>
              <Button type="button" variant="outline" onClick={() => setCreateOpen(false)}>
                {t("common.cancel")}
              </Button>
              <Button type="submit" disabled={createMutation.isPending}>
                {t("alerts.create")}
              </Button>
            </DialogFooter>
          </form>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <Dialog open={!!deleteConfirmId} onOpenChange={() => setDeleteConfirmId(null)}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("alerts.deleteConfirm")}</DialogTitle>
          </DialogHeader>
          <p className="text-sm text-muted-foreground">
            {t("alerts.deleteConfirmDesc")}
          </p>
          <DialogFooter>
            <Button variant="outline" onClick={() => setDeleteConfirmId(null)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              onClick={() => deleteConfirmId && deleteMutation.mutate(deleteConfirmId)}
              disabled={deleteMutation.isPending}
            >
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}

function TimelineCard({
  event,
  locale,
  productId,
  onAutoResponse,
  onViewProduct,
}: {
  event: AlertEvent;
  locale: string;
  productId: string | null;
  onAutoResponse: () => void;
  onViewProduct: () => void;
}) {
  const { t } = useTranslation();
  const type = getEventType(event);
  const priority = getEventPriority(event, type);
  const Icon = ALERT_TYPE_ICONS[type];
  const stripeClass = PRIORITY_STRIPE[priority];
  const aiExplanation = event.message ?? null;

  let titleKey = ALERT_TYPE_KEYS[type];
  let title: string;
  if (type === "price_drop" && event.old_price != null && event.new_price != null) {
    const pct = (((event.old_price - event.new_price) / event.old_price) * 100).toFixed(0);
    titleKey = "alerts.titlePriceDropped";
    title = t(titleKey, { percent: pct });
  } else if (type === "price_increase" && event.old_price != null && event.new_price != null) {
    const pct = (((event.new_price - event.old_price) / event.old_price) * 100).toFixed(0);
    titleKey = "alerts.titlePriceIncreased";
    title = t(titleKey, { percent: pct });
  } else {
    title = t(titleKey);
  }

  const marketplace = event.competitor_name?.toLowerCase().includes("ozon")
    ? "Ozon"
    : event.competitor_name?.toLowerCase().includes("wb") || event.competitor_name?.toLowerCase().includes("wildberries")
      ? "WB"
      : event.competitor_name?.toLowerCase().includes("kaspi")
        ? "Kaspi"
        : event.competitor_name ?? "—";

  return (
    <div
      className={cn(
        "flex overflow-hidden rounded-lg border border-border bg-card shadow-sm dark:border-border dark:bg-card",
        "border-l-4",
        stripeClass
      )}
    >
      <div className="flex flex-1 flex-col gap-3 p-4">
        <div className="flex items-start gap-3">
          <Icon className="mt-0.5 size-5 shrink-0 text-muted-foreground" />
          <div className="min-w-0 flex-1">
            <h4 className="font-semibold">{title}</h4>
            <p className="mt-1 text-sm text-muted-foreground">
              {event.product_name ?? t("alerts.product")} · {event.competitor_name ?? t("dashboard.competitor")} · {marketplace}
            </p>
            {aiExplanation && (
              <p className="mt-2 italic text-sm text-muted-foreground">
                {aiExplanation}
              </p>
            )}
          </div>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="text-xs text-muted-foreground">
            {formatRelativeTime(event.triggered_at, locale)}
          </span>
          <Button variant="outline" size="sm" onClick={onAutoResponse}>
            {t("alerts.autoResponse")}
          </Button>
          {productId && (
            <Button variant="outline" size="sm" onClick={onViewProduct}>
              {t("alerts.viewProduct")}
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}

function AlertRuleCompact({
  alert,
  onToggle,
  onEdit,
  onDelete,
}: {
  alert: Alert;
  onToggle: (enabled: boolean) => void;
  onEdit: () => void;
  onDelete: () => void;
}) {
  const { t } = useTranslation();
  const type = alert.type as AlertType;

  const channelIcons = [];
  if (alert.channel === "email" || alert.channel === "both") channelIcons.push(Mail);
  if (alert.channel === "telegram" || alert.channel === "both") channelIcons.push(MessageCircle);

  return (
    <div className="flex items-center justify-between gap-2 rounded-md border border-border bg-background/50 px-3 py-2 dark:border-border dark:bg-background/30">
      <div className="min-w-0 flex-1">
        <p className="truncate text-sm font-medium">
          {t(ALERT_TYPE_KEYS[type] ?? alert.type)}
        </p>
        <p className="truncate text-xs text-muted-foreground">
          {alert.product_name ?? t("alerts.allProducts")}
          {alert.threshold_percent != null && ` · ${alert.threshold_percent}%`}
        </p>
      </div>
      <div className="flex shrink-0 items-center gap-1">
        {channelIcons.map((Icon, i) => (
          <Icon key={i} className="size-3.5 text-muted-foreground" />
        ))}
        <Switch checked={alert.is_active} onCheckedChange={onToggle} />
        <Button variant="ghost" size="icon" className="size-8" onClick={onEdit} aria-label={t("common.edit")}>
          <Pencil className="size-3.5" />
        </Button>
        <Button variant="ghost" size="icon" className="size-8" onClick={onDelete} aria-label={t("common.delete")}>
          <Trash2 className="size-3.5" />
        </Button>
      </div>
    </div>
  );
}
