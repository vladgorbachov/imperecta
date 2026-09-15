/**
 * Alerts — client price-alert rules and their event feed.
 *
 * The alerts backend (CRUD + events, DB table `alerts` already exists) is
 * pending — contracts in docs/FRONTEND_BACKEND_REQUESTS.md. Until it lands
 * both tabs render honest empty states and the create-rule form is
 * intentionally non-submittable. No mock data.
 */

import { useState } from "react";
import { useTranslation } from "react-i18next";
import { Bell, BellRing, Plus } from "lucide-react";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { PageHeader } from "@/components/ui-custom/PageHeader";
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
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";

const ALERT_TYPES = ["price_drop", "price_rise", "availability"] as const;
const CHANNELS = ["email", "telegram", "webhook"] as const;

/** Static key maps — the i18n coverage guard forbids template-literal keys. */
const ALERT_TYPE_LABELS: Record<(typeof ALERT_TYPES)[number], string> = {
  price_drop: "alerts.type.price_drop",
  price_rise: "alerts.type.price_rise",
  availability: "alerts.type.availability",
};
const CHANNEL_LABELS: Record<(typeof CHANNELS)[number], string> = {
  email: "alerts.channel.email",
  telegram: "alerts.channel.telegram",
  webhook: "alerts.channel.webhook",
};

function CreateRuleDialog({
  open,
  onOpenChange,
}: {
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const { t } = useTranslation();
  const [alertType, setAlertType] = useState<(typeof ALERT_TYPES)[number]>("price_drop");
  const [channel, setChannel] = useState<(typeof CHANNELS)[number]>("email");

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="surface-overlay sm:max-w-md">
        <DialogHeader>
          <DialogTitle>{t("alerts.create.title")}</DialogTitle>
        </DialogHeader>
        <div className="space-y-3">
          <div className="space-y-1.5">
            <label className="label-mono block">{t("alerts.create.product")}</label>
            <Input placeholder={t("products.searchByName")} disabled />
          </div>
          <div className="grid grid-cols-2 gap-3">
            <div className="space-y-1.5">
              <label className="label-mono block">{t("alerts.create.type")}</label>
              <Select
                value={alertType}
                onValueChange={(value) => setAlertType(value as typeof alertType)}
              >
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
              <Input type="number" inputMode="decimal" placeholder="5" disabled />
            </div>
          </div>
          <div className="space-y-1.5">
            <label className="label-mono block">{t("alerts.create.channel")}</label>
            <Select
              value={channel}
              onValueChange={(value) => setChannel(value as typeof channel)}
            >
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
          <Button className="w-full" disabled>
            {t("alerts.create.submit")}
          </Button>
          <p className="text-center text-xs text-muted-foreground">
            {t("alerts.backendPending")}
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
}

export function AlertsPage() {
  const { t } = useTranslation();
  const [tab, setTab] = useState<"rules" | "events">("rules");
  const [createOpen, setCreateOpen] = useState(false);

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
          </TabsTrigger>
          <TabsTrigger value="events" className="rounded-md px-3 text-xs">
            {t("alerts.tabs.events")}
          </TabsTrigger>
        </TabsList>

        <TabsContent value="rules" className="mt-0 flex-1">
          <div className="surface-base rounded-xl">
            <EmptyState
              icon={Bell}
              title="alerts.rules.empty"
              description="alerts.rules.emptyHint"
            />
          </div>
        </TabsContent>

        <TabsContent value="events" className="mt-0 flex-1">
          <div className="surface-base rounded-xl">
            <EmptyState
              icon={BellRing}
              title="alerts.events.empty"
              description="alerts.events.emptyHint"
            />
          </div>
        </TabsContent>
      </Tabs>

      <CreateRuleDialog open={createOpen} onOpenChange={setCreateOpen} />
    </div>
  );
}
