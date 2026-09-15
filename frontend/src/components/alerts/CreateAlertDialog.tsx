/**
 * Create-alert-rule dialog (P3, live backend).
 * Used from the Alerts page (with a product picker) and from Product Peek
 * (prefilled with the peek's listing — picker hidden).
 */

import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { toast } from "sonner";
import { Check, Search } from "lucide-react";
import type { AlertChannel, AlertType } from "@/api/alerts";
import { useCreateAlertRule } from "@/hooks/useAlerts";
import { usePoolProducts } from "@/hooks/usePoolProducts";
import { useDebounce } from "@/hooks/useDebounce";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { cn } from "@/lib/utils";

const ALERT_TYPES: AlertType[] = ["price_drop", "price_rise", "availability"];
const CHANNELS: AlertChannel[] = ["email", "telegram", "webhook"];

/** Static key maps — the i18n coverage guard forbids template-literal keys. */
const ALERT_TYPE_LABELS: Record<AlertType, string> = {
  price_drop: "alerts.type.price_drop",
  price_rise: "alerts.type.price_rise",
  availability: "alerts.type.availability",
};
const CHANNEL_LABELS: Record<AlertChannel, string> = {
  email: "alerts.channel.email",
  telegram: "alerts.channel.telegram",
  webhook: "alerts.channel.webhook",
};

export interface CreateAlertDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  /** When set (e.g. from Product Peek) the product picker is hidden. */
  prefill?: { listingId: string; title: string } | null;
}

export function CreateAlertDialog({ open, onOpenChange, prefill }: CreateAlertDialogProps) {
  const { t } = useTranslation();
  const createRule = useCreateAlertRule();

  const [productQuery, setProductQuery] = useState("");
  const [picked, setPicked] = useState<{ listingId: string; title: string } | null>(null);
  const [alertType, setAlertType] = useState<AlertType>("price_drop");
  const [channel, setChannel] = useState<AlertChannel>("email");
  const [threshold, setThreshold] = useState("5");
  const [webhookUrl, setWebhookUrl] = useState("");

  const debouncedQuery = useDebounce(productQuery, 300);
  const searchEnabled = open && !prefill && debouncedQuery.trim().length >= 2;
  const { data: searchData } = usePoolProducts(
    { search: searchEnabled ? debouncedQuery.trim() : undefined, limit: 6, offset: 0 },
    { enabled: searchEnabled },
  );

  const target = prefill ?? picked;
  const needsThreshold = alertType !== "availability";
  const thresholdValue = Number(threshold);
  const thresholdValid =
    !needsThreshold || (Number.isFinite(thresholdValue) && thresholdValue > 0 && thresholdValue <= 100);
  const webhookValid = channel !== "webhook" || webhookUrl.startsWith("https://");
  const canSubmit = !!target && thresholdValid && webhookValid && !createRule.isPending;

  const reset = () => {
    setProductQuery("");
    setPicked(null);
    setAlertType("price_drop");
    setChannel("email");
    setThreshold("5");
    setWebhookUrl("");
  };

  const submit = async () => {
    if (!target) {
      return;
    }
    try {
      await createRule.mutateAsync({
        listing_id: target.listingId,
        alert_type: alertType,
        threshold_pct: needsThreshold ? thresholdValue : null,
        channel,
        webhook_url: channel === "webhook" ? webhookUrl : null,
        cooldown_minutes: 60,
      });
      toast.success(t("alerts.toast.created"));
      reset();
      onOpenChange(false);
    } catch {
      toast.error(t("common.error"));
    }
  };

  const searchItems = useMemo(() => searchData?.items ?? [], [searchData?.items]);

  return (
    <Dialog
      open={open}
      onOpenChange={(next) => {
        if (!next) {
          reset();
        }
        onOpenChange(next);
      }}
    >
      <DialogContent className="surface-overlay sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("alerts.create.title")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="label-mono block">{t("alerts.create.product")}</label>
            {target ? (
              <div className="flex items-center gap-2 rounded-md border border-[var(--accent-border)] bg-[var(--accent-bg-subtle)] px-3 py-2 text-sm">
                <Check className="size-3.5 shrink-0 text-[var(--accent)]" />
                <span className="min-w-0 flex-1 truncate">{target.title}</span>
                {!prefill && (
                  <button
                    type="button"
                    className="shrink-0 text-xs text-muted-foreground hover:text-[var(--foreground)]"
                    onClick={() => setPicked(null)}
                  >
                    {t("common.edit")}
                  </button>
                )}
              </div>
            ) : (
              <div className="space-y-1">
                <div className="relative">
                  <Search className="pointer-events-none absolute left-2.5 top-1/2 size-3.5 -translate-y-1/2 text-muted-foreground" />
                  <Input
                    value={productQuery}
                    onChange={(event) => setProductQuery(event.target.value)}
                    placeholder={t("products.searchByName")}
                    className="pl-8"
                  />
                </div>
                {searchEnabled && searchItems.length > 0 ? (
                  <div className="max-h-40 overflow-y-auto rounded-md border border-[var(--glass-border)]">
                    {searchItems.map((item) => (
                      <button
                        key={item.id}
                        type="button"
                        className="flex w-full items-center gap-2 px-3 py-2 text-left text-sm hover:bg-[var(--glass-bg-hover)]"
                        onClick={() =>
                          setPicked({ listingId: item.id, title: item.title ?? item.url })
                        }
                      >
                        <span className="min-w-0 flex-1 truncate">
                          {item.title ?? item.url}
                        </span>
                        <span className="shrink-0 text-xs text-muted-foreground">
                          {item.marketplace_name ?? item.marketplace_domain}
                        </span>
                      </button>
                    ))}
                  </div>
                ) : null}
              </div>
            )}
          </div>

          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="label-mono block">{t("alerts.create.type")}</label>
              <Select value={alertType} onValueChange={(value) => setAlertType(value as AlertType)}>
                <SelectTrigger className="h-9">
                  <SelectValue />
                </SelectTrigger>
                <SelectContent>
                  {ALERT_TYPES.map((value) => (
                    <SelectItem key={value} value={value}>
                      {t(ALERT_TYPE_LABELS[value])}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
            </div>
            <div className="space-y-1.5">
              <label className="label-mono block">{t("alerts.create.threshold")}</label>
              <Input
                type="number"
                inputMode="decimal"
                value={threshold}
                onChange={(event) => setThreshold(event.target.value)}
                disabled={!needsThreshold}
                className={cn(!thresholdValid && "border-[var(--status-error-border)]")}
              />
            </div>
          </div>

          <div className="space-y-1.5">
            <label className="label-mono block">{t("alerts.create.channel")}</label>
            <Select value={channel} onValueChange={(value) => setChannel(value as AlertChannel)}>
              <SelectTrigger className="h-9">
                <SelectValue />
              </SelectTrigger>
              <SelectContent>
                {CHANNELS.map((value) => (
                  <SelectItem key={value} value={value}>
                    {t(CHANNEL_LABELS[value])}
                  </SelectItem>
                ))}
              </SelectContent>
            </Select>
          </div>

          {channel === "webhook" ? (
            <div className="space-y-1.5">
              <label className="label-mono block">{t("alerts.create.webhookUrl")}</label>
              <Input
                type="url"
                value={webhookUrl}
                onChange={(event) => setWebhookUrl(event.target.value)}
                placeholder="https://…"
                className={cn(!webhookValid && webhookUrl !== "" && "border-[var(--status-error-border)]")}
              />
            </div>
          ) : null}

          <Button className="w-full" disabled={!canSubmit} onClick={() => void submit()}>
            {t("alerts.create.submit")}
          </Button>
        </div>
      </DialogContent>
    </Dialog>
  );
}
