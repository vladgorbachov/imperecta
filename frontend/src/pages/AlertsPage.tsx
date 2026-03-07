/**
 * Alerts page: active rules section + event history timeline.
 *
 * i18n keys used:
 * - nav.alerts
 * - alerts.activeRules, alerts.createRule, alerts.eventHistory
 * - alerts.typePriceDrop, alerts.typePriceIncrease, alerts.typeOutOfStock, alerts.typeNewPromo
 * - alerts.threshold, alerts.channelEmail, alerts.channelTelegram, alerts.channelBoth
 * - alerts.noAlerts, alerts.noEvents, alerts.eventHistoryEmpty, alerts.eventHistoryEmptyHint
 * - alerts.createAlert, alerts.create, alerts.createSuccess, alerts.createError
 * - alerts.product, alerts.allProducts, alerts.thresholdPlaceholder
 * - common.cancel, common.delete, common.confirm
 * - products.search, products.noResults
 * - dashboard.competitor
 * - ui.priceChangeArrow
 */

import { useState, useRef, useEffect } from "react";
import { useTranslation } from "react-i18next";
import {
  Plus,
  Pencil,
  Trash2,
  Mail,
  MessageCircle,
  History,
} from "lucide-react";
import { formatShortDateTime } from "@/lib/formatters";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { alertsApi } from "@/api/alerts";
import { productsApi } from "@/api/products";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
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
import { Separator } from "@/components/ui/separator";
import { PriceChangeCell } from "@/components/ui-custom/PriceChangeCell";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { cn } from "@/lib/utils";
import { toast } from "sonner";
import type { Alert, AlertEvent } from "@/api/alerts";

type AlertType = "price_drop" | "price_increase" | "out_of_stock" | "new_promo";
type AlertChannel = "email" | "telegram" | "both";

const ALERT_TYPE_KEYS: Record<AlertType, string> = {
  price_drop: "alerts.typePriceDrop",
  price_increase: "alerts.typePriceIncrease",
  out_of_stock: "alerts.typeOutOfStock",
  new_promo: "alerts.typeNewPromo",
};

const ALERT_TYPE_COLORS: Record<AlertType, string> = {
  price_drop: "bg-price-down/15 text-price-down border-price-down/30 dark:bg-price-down/20 dark:text-price-down dark:border-price-down/40",
  price_increase: "bg-price-up/15 text-price-up border-price-up/30 dark:bg-price-up/20 dark:text-price-up dark:border-price-up/40",
  out_of_stock: "bg-out-of-stock/15 text-out-of-stock border-out-of-stock/30 dark:bg-out-of-stock/20 dark:text-out-of-stock dark:border-out-of-stock/40",
  new_promo: "bg-promo/15 text-promo border-promo/30 dark:bg-promo/20 dark:text-promo dark:border-promo/40",
};

const ALERT_TYPE_BORDER: Record<AlertType, string> = {
  price_drop: "border-l-price-down dark:border-l-price-down",
  price_increase: "border-l-price-up dark:border-l-price-up",
  out_of_stock: "border-l-out-of-stock dark:border-l-out-of-stock",
  new_promo: "border-l-promo dark:border-l-promo",
};

const CHANNEL_KEYS: Record<AlertChannel, string> = {
  email: "alerts.channelEmail",
  telegram: "alerts.channelTelegram",
  both: "alerts.channelBoth",
};

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
  const locale = i18n.language;
  const queryClient = useQueryClient();
  const [createOpen, setCreateOpen] = useState(false);
  const [editAlert, setEditAlert] = useState<Alert | null>(null);
  const [deleteConfirmId, setDeleteConfirmId] = useState<string | null>(null);
  const [form, setForm] = useState({
    product_id: "",
    type: "price_drop" as AlertType,
    threshold_percent: "",
    channel: "email" as AlertChannel,
  });

  const { data: alerts = [], isLoading: alertsLoading } = useQuery({
    queryKey: ["alerts"],
    queryFn: async () => {
      const { data } = await alertsApi.list();
      return data;
    },
  });

  const { data: events = [], isLoading: eventsLoading } = useQuery({
    queryKey: ["alerts", "events"],
    queryFn: async () => {
      const { data } = await alertsApi.getEvents(20);
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
    const payload = {
      product_id: form.product_id || undefined,
      type: form.type,
      threshold_percent: form.threshold_percent ? parseFloat(form.threshold_percent) : undefined,
      channel: form.channel,
    };
    if (editAlert) {
      createMutation.mutate(payload);
    } else {
      createMutation.mutate(payload);
    }
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

  return (
    <div className="space-y-6">
      <PageHeader title="nav.alerts" />

      {/* Section 1: Active rules */}
      <section>
        <div className="flex flex-wrap items-center justify-between gap-4">
          <div className="flex items-center gap-2">
            <h2 className="text-lg font-semibold">{t("alerts.activeRules")}</h2>
            <Badge variant="secondary">{alerts.length}</Badge>
          </div>
          <Button onClick={() => { setEditAlert(null); setForm({ product_id: "", type: "price_drop", threshold_percent: "", channel: "email" }); setCreateOpen(true); }}>
            <Plus className="mr-2 size-4" />
            {t("alerts.createRule")}
          </Button>
        </div>
        <div className="mt-4 space-y-2">
          {alertsLoading ? (
            Array.from({ length: 3 }).map((_, i) => (
              <div key={i} className="h-16 animate-pulse rounded-lg border bg-muted" />
            ))
          ) : alerts.length === 0 ? (
            <p className="py-8 text-center text-sm text-muted-foreground">
              {t("alerts.noAlerts")}
            </p>
          ) : (
            alerts.map((a) => (
              <AlertRuleItem
                key={a.id}
                alert={a}
                onToggle={(enabled) => updateMutation.mutate({ id: a.id, is_active: enabled })}
                onEdit={() => openEdit(a)}
                onDelete={() => setDeleteConfirmId(a.id)}
              />
            ))
          )}
        </div>
      </section>

      <Separator />

      {/* Section 2: Event history */}
      <section>
        <h2 className="mb-4 text-lg font-semibold">{t("alerts.eventHistory")}</h2>
        {eventsLoading ? (
          <div className="space-y-4">
            {Array.from({ length: 5 }).map((_, i) => (
              <div key={i} className="flex gap-4">
                <div className="h-12 w-24 shrink-0 animate-pulse rounded bg-muted" />
                <div className="h-20 flex-1 animate-pulse rounded-lg border bg-muted" />
              </div>
            ))}
          </div>
        ) : events.length === 0 ? (
          <EmptyState
            title="alerts.eventHistoryEmpty"
            description="alerts.eventHistoryEmptyHint"
            icon={History}
          />
        ) : (
          <div className="relative">
            <div className="absolute left-4 top-0 bottom-0 w-px bg-border dark:bg-border" />
            <div className="space-y-0">
              {events.map((ev) => (
                <TimelineEventItem key={ev.id} event={ev} locale={locale} />
              ))}
            </div>
          </div>
        )}
      </section>

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
                        <span className={cn("rounded border px-2 py-0.5 text-xs", ALERT_TYPE_COLORS[typeKey])}>
                          {t(ALERT_TYPE_KEYS[typeKey])}
                        </span>
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
          <p className="text-sm text-muted-foreground dark:text-muted-foreground">
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

function AlertRuleItem({
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
  const typeColor = ALERT_TYPE_COLORS[type] ?? "bg-muted";

  const channelIcons = [];
  if (alert.channel === "email" || alert.channel === "both") channelIcons.push(Mail);
  if (alert.channel === "telegram" || alert.channel === "both") channelIcons.push(MessageCircle);

  return (
    <div className="flex flex-wrap items-center justify-between gap-4 rounded-lg border border-border bg-card p-4 dark:border-border dark:bg-card">
      <div className="flex flex-1 flex-wrap items-center gap-3">
        <Badge className={cn("border", typeColor)}>
          {t(ALERT_TYPE_KEYS[type] ?? alert.type)}
        </Badge>
        {alert.product_id ? (
          <a
            href={`/products/${alert.product_id}`}
            className="text-sm font-medium text-primary hover:underline dark:text-primary"
          >
            {alert.product_name ?? t("alerts.allProducts")}
          </a>
        ) : (
          <span className="text-sm font-medium">
            {alert.product_name ?? t("alerts.allProducts")}
          </span>
        )}
        {alert.threshold_percent != null && (
          <span className="text-sm text-muted-foreground dark:text-muted-foreground">
            &gt; {alert.threshold_percent}%
          </span>
        )}
        <div className="flex items-center gap-1">
          {channelIcons.map((Icon, i) => (
            <Icon key={i} className="size-4 text-muted-foreground dark:text-muted-foreground" />
          ))}
        </div>
      </div>
      <div className="flex items-center gap-2">
        <Switch checked={alert.is_active} onCheckedChange={onToggle} />
        <Button
          variant="ghost"
          size="icon"
          onClick={onEdit}
          aria-label={t("common.edit")}
        >
          <Pencil className="size-4" />
        </Button>
        <Button
          variant="ghost"
          size="icon"
          onClick={onDelete}
          aria-label={t("common.delete")}
        >
          <Trash2 className="size-4" />
        </Button>
      </div>
    </div>
  );
}

function TimelineEventItem({ event, locale }: { event: AlertEvent; locale: string }) {
  const { t } = useTranslation();
  const type: AlertType =
    event.old_price != null && event.new_price != null
      ? event.new_price < event.old_price
        ? "price_drop"
        : "price_increase"
      : event.message?.toLowerCase().includes("promo")
        ? "new_promo"
        : "out_of_stock";
  const borderClass = ALERT_TYPE_BORDER[type] ?? "border-l-muted";

  const ChannelIcon = event.sent_via?.toLowerCase().includes("telegram") ? MessageCircle : Mail;

  return (
    <div className="relative flex gap-4 pb-8">
      <div className="relative z-10 flex w-24 shrink-0 flex-col items-end pt-1">
        <span className="text-sm text-muted-foreground dark:text-muted-foreground">
          {formatShortDateTime(event.triggered_at, locale)}
        </span>
      </div>
      <div className="flex-1">
        <div
          className={cn(
            "rounded-lg border border-l-4 border-border bg-card p-4 dark:border-border dark:bg-card",
            borderClass
          )}
        >
          <div className="flex flex-wrap items-center gap-2">
            <Badge className={cn("border", ALERT_TYPE_COLORS[type])}>
              {t(ALERT_TYPE_KEYS[type] ?? "alerts.typePriceDrop")}
            </Badge>
            <span className="text-sm">
              {event.product_name ?? t("alerts.product")} → {event.competitor_name ?? t("dashboard.competitor")}
            </span>
            {event.old_price != null && event.new_price != null && (
              <PriceChangeCell oldPrice={event.old_price} newPrice={event.new_price} />
            )}
            <ChannelIcon className="size-4 text-muted-foreground dark:text-muted-foreground" />
          </div>
        </div>
      </div>
    </div>
  );
}
