/**
 * Settings page: Profile, Telegram, Notifications, AI Personalization, Plan sections.
 * Sections separated by shadcn Separator.
 *
 * i18n keys used:
 * - nav.settings, settings.*, auth.*, common.*
 */

import { useState, useEffect } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Zap } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { analyticsApi } from "@/api/analytics";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import type { LanguageCode } from "@/i18n";
import { RadioGroup, RadioGroupItemStyled } from "@/components/ui/radio-group";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const BOT_USERNAME = "@ImperectaBot";
const BOT_URL = "https://t.me/ImperectaBot";
const CODE_DURATION_SEC = 300;
const PLAN_LIMITS: Record<string, { products: number; competitors: number }> = {
  trial: { products: 50, competitors: 15 },
  starter: { products: 50, competitors: 15 },
  business: { products: 100, competitors: 30 },
  pro: { products: 999, competitors: 999 },
};

const TRIAL_DAYS_TOTAL = 14;

const DIGEST_HOURS = Array.from({ length: 13 }, (_, i) => i + 8);

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const updateLanguage = useAuthStore((s) => s.updateLanguage);

  const [profileForm, setProfileForm] = useState({ name: "", company_name: "" });
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [codeSecondsLeft, setCodeSecondsLeft] = useState(0);
  const [notifChannel, setNotifChannel] = useState<"email" | "telegram" | "both">("both");
  const [digestHour, setDigestHour] = useState("10");
  const [digestTone, setDigestTone] = useState<"conservative" | "balanced" | "aggressive">(
    "balanced"
  );

  const { data: userData, isLoading } = useQuery({
    queryKey: ["user", "me"],
    queryFn: async () => {
      const { data } = await authApi.getMe();
      return data;
    },
  });

  const { data: summary } = useQuery({
    queryKey: ["analytics", "dashboard", "summary"],
    queryFn: () => analyticsApi.getDashboardSummary().then((r) => r.data),
  });

  const user = useAuthStore((s) => s.user);
  const u = user ?? userData;

  useEffect(() => {
    if (u) {
      setProfileForm({ name: u.name, company_name: u.company_name ?? "" });
    }
  }, [u?.id]);

  useEffect(() => {
    if (telegramCode && codeSecondsLeft > 0) {
      const id = setInterval(() => setCodeSecondsLeft((s) => Math.max(0, s - 1)), 1000);
      return () => clearInterval(id);
    }
  }, [telegramCode, codeSecondsLeft]);

  const updateMutation = useMutation({
    mutationFn: async (data: { name?: string; company_name?: string; language?: string }) => {
      const res = await authApi.updateMe(data);
      return res.data;
    },
    onSuccess: (updatedUser) => {
      if (updatedUser) setUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      toast.success(t("auth.profileUpdated"));
    },
    onError: () => toast.error(t("auth.updateFailed")),
  });

  const telegramLinkMutation = useMutation({
    mutationFn: async () => {
      const { data } = await authApi.getTelegramLink();
      return data;
    },
    onSuccess: (data) => {
      setTelegramCode(data.code);
      setCodeSecondsLeft(CODE_DURATION_SEC);
      toast.success(t("auth.codeGenerated"));
    },
    onError: () => toast.error(t("auth.codeError")),
  });

  const disconnectMutation = useMutation({
    mutationFn: () => authApi.disconnectTelegram(),
    onSuccess: async () => {
      const { data } = await authApi.getMe();
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      setTelegramCode(null);
      setCodeSecondsLeft(0);
      toast.success(t("settings.telegramDisconnectedSuccess"));
    },
    onError: () => toast.error(t("auth.updateFailed")),
  });

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({
      name: profileForm.name,
      company_name: profileForm.company_name || undefined,
    });
  };

  const handleLanguageChange = (code: LanguageCode) => {
    updateLanguage(code);
  };

  const handleCopyCode = () => {
    if (telegramCode) {
      navigator.clipboard.writeText(telegramCode);
      toast.success(t("common.copied"));
    }
  };

  const plan = (u?.plan ?? "trial").toLowerCase();
  const limits = PLAN_LIMITS[plan] ?? PLAN_LIMITS.trial;
  const productsCount = summary?.total_products ?? 0;
  const competitorsCount = summary?.total_competitors ?? 0;
  const productsPercent = limits.products > 0 ? (productsCount / limits.products) * 100 : 0;
  const competitorsPercent = limits.competitors > 0 ? (competitorsCount / limits.competitors) * 100 : 0;
  const productsVariant = productsPercent >= 95 ? "danger" : productsPercent >= 80 ? "warning" : "default";
  const competitorsVariant = competitorsPercent >= 95 ? "danger" : competitorsPercent >= 80 ? "warning" : "default";

  const trialEndsAt = u?.trial_ends_at ? new Date(u.trial_ends_at) : null;
  const trialDaysLeft = trialEndsAt
    ? Math.max(0, Math.ceil((trialEndsAt.getTime() - Date.now()) / (24 * 60 * 60 * 1000)))
    : 0;

  const formatCountdown = (sec: number) => {
    const m = Math.floor(sec / 60);
    const s = sec % 60;
    return `${m}:${s.toString().padStart(2, "0")}`;
  };

  return (
    <div className="mx-auto max-w-2xl space-y-6">
      <PageHeader title="nav.settings" />

      {isLoading ? (
        <Skeleton className="h-64 w-full" />
      ) : (
        <>
          <Card>
            <CardHeader>
              <CardTitle>{t("settings.profile")}</CardTitle>
              <CardDescription>{t("settings.profileDescription")}</CardDescription>
            </CardHeader>
            <CardContent>
              <form onSubmit={handleProfileSubmit} className="space-y-4">
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("auth.name")}</label>
                  <Input
                    value={profileForm.name}
                    onChange={(e) => setProfileForm((f) => ({ ...f, name: e.target.value }))}
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("auth.companyName")}</label>
                  <Input
                    value={profileForm.company_name}
                    onChange={(e) =>
                      setProfileForm((f) => ({ ...f, company_name: e.target.value }))
                    }
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("auth.email")}</label>
                  <div className="flex flex-wrap items-center gap-2">
                    <Input
                      value={u?.email ?? ""}
                      disabled
                      className="flex-1 bg-muted dark:bg-muted"
                    />
                    <Badge className="bg-green-500/15 text-green-700 border-green-500/30 dark:bg-green-500/20 dark:text-green-400 dark:border-green-500/40">
                      {t("settings.emailVerified")}
                    </Badge>
                  </div>
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("auth.language")}</label>
                  <LanguageSelector
                    value={(u?.language as LanguageCode) ?? (i18n.language as LanguageCode)}
                    onChange={handleLanguageChange}
                    showFlags
                    compact={false}
                  />
                </div>
                <Button type="submit" disabled={updateMutation.isPending}>
                  {updateMutation.isPending ? t("common.loading") : t("common.save")}
                </Button>
              </form>
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>{t("settings.telegram")}</CardTitle>
              <CardDescription>{t("settings.telegramDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {u?.telegram_chat_id ? (
                <div className="flex flex-wrap items-center justify-between gap-4">
                  <div className="flex items-center gap-2">
                    <span
                      className="size-2.5 rounded-full bg-green-500 dark:bg-green-500"
                      aria-hidden
                    />
                    <span className="font-medium">{t("settings.telegramConnected")}</span>
                    <span className="text-muted-foreground dark:text-muted-foreground">
                      {BOT_USERNAME}
                    </span>
                  </div>
                  <Button
                    variant="outline"
                    size="sm"
                    onClick={() => disconnectMutation.mutate()}
                    disabled={disconnectMutation.isPending}
                  >
                    {t("settings.telegramDisconnect")}
                  </Button>
                </div>
              ) : (
                <>
                  {telegramCode ? (
                    <div className="space-y-4 rounded-lg border border-border bg-muted/30 p-4 dark:bg-muted/20">
                      <div className="flex items-center justify-between gap-4">
                        <span
                          className="font-mono text-2xl font-bold tracking-widest sm:text-3xl"
                          aria-label={telegramCode}
                        >
                          {telegramCode}
                        </span>
                        <Button
                          variant="outline"
                          size="icon"
                          onClick={handleCopyCode}
                          aria-label={t("common.copy")}
                        >
                          <Copy className="size-4" />
                        </Button>
                      </div>
                      <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                        {t("settings.codeInstruction", { bot: BOT_USERNAME })}
                      </p>
                      <a
                        href={BOT_URL}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="block text-sm text-primary hover:underline dark:text-primary"
                      >
                        {BOT_URL}
                      </a>
                      <p className="font-mono text-lg font-medium">
                        {formatCountdown(codeSecondsLeft)}
                      </p>
                    </div>
                  ) : (
                    <div className="flex items-center gap-2">
                      <span
                        className="size-2.5 rounded-full bg-neutral-400 dark:bg-neutral-500"
                        aria-hidden
                      />
                      <span className="text-muted-foreground dark:text-muted-foreground">
                        {t("settings.telegramDisconnected")}
                      </span>
                    </div>
                  )}
                  <Button
                    variant="outline"
                    onClick={() => telegramLinkMutation.mutate()}
                    disabled={telegramLinkMutation.isPending}
                  >
                    {t("settings.getLinkCode")}
                  </Button>
                </>
              )}
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>{t("settings.notifications")}</CardTitle>
              <CardDescription>{t("settings.notificationsDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("alerts.channel")}</label>
                <RadioGroup
                  value={notifChannel}
                  onValueChange={(v) => setNotifChannel(v as "email" | "telegram" | "both")}
                  className="flex flex-wrap gap-4"
                >
                  <label className="flex cursor-pointer items-center gap-2">
                    <RadioGroupItemStyled value="email" />
                    <span>{t("settings.channelEmail")}</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <RadioGroupItemStyled value="telegram" />
                    <span>{t("settings.channelTelegram")}</span>
                  </label>
                  <label className="flex cursor-pointer items-center gap-2">
                    <RadioGroupItemStyled value="both" />
                    <span>{t("settings.channelBoth")}</span>
                  </label>
                </RadioGroup>
              </div>
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("settings.digestTime")}</label>
                <Select value={digestHour} onValueChange={setDigestHour}>
                  <SelectTrigger>
                    <SelectValue />
                  </SelectTrigger>
                  <SelectContent>
                    {DIGEST_HOURS.map((h) => (
                      <SelectItem key={h} value={String(h)}>
                        {h.toString().padStart(2, "0")}:00
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              </div>
              <Button>{t("common.save")}</Button>
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>{t("settings.aiPersonalization")}</CardTitle>
              <CardDescription>{t("settings.aiPersonalizationDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="space-y-2">
                <label className="text-sm font-medium">{t("settings.digestTone")}</label>
                <RadioGroup
                  value={digestTone}
                  onValueChange={(v) =>
                    setDigestTone(v as "conservative" | "balanced" | "aggressive")
                  }
                  className="flex flex-col gap-3"
                >
                  <label className="flex cursor-pointer items-start gap-2">
                    <RadioGroupItemStyled value="conservative" className="mt-0.5" />
                    <div>
                      <span className="font-medium">{t("settings.digestToneConservative")}</span>
                      <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                        {t("settings.digestToneConservativeDesc")}
                      </p>
                    </div>
                  </label>
                  <label className="flex cursor-pointer items-start gap-2">
                    <RadioGroupItemStyled value="balanced" className="mt-0.5" />
                    <div>
                      <span className="font-medium">{t("settings.digestToneBalanced")}</span>
                      <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                        {t("settings.digestToneBalancedDesc")}
                      </p>
                    </div>
                  </label>
                  <label className="flex cursor-pointer items-start gap-2">
                    <RadioGroupItemStyled value="aggressive" className="mt-0.5" />
                    <div>
                      <span className="font-medium">{t("settings.digestToneAggressive")}</span>
                      <p className="text-xs text-muted-foreground dark:text-muted-foreground">
                        {t("settings.digestToneAggressiveDesc")}
                      </p>
                    </div>
                  </label>
                </RadioGroup>
              </div>
              {/* TODO: save to user profile, use in Claude prompt */}
            </CardContent>
          </Card>

          <Separator />

          <Card>
            <CardHeader>
              <CardTitle>{t("settings.plan")}</CardTitle>
              <CardDescription>{t("settings.planDescription")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              <div className="flex items-center gap-2">
                <Badge
                  className={cn(
                    plan === "trial" &&
                      "bg-amber-500/15 text-amber-700 border-amber-500/30 dark:bg-amber-500/20 dark:text-amber-400 dark:border-amber-500/40",
                    plan === "starter" &&
                      "bg-blue-500/15 text-blue-700 border-blue-500/30 dark:bg-blue-500/20 dark:text-blue-400 dark:border-blue-500/40",
                    (plan === "business" || plan === "pro") &&
                      "bg-primary/15 text-primary border-primary/30 dark:bg-primary/20 dark:text-primary dark:border-primary/40"
                  )}
                >
                  {plan === "trial"
                    ? t("settings.planTrial")
                    : plan === "starter"
                      ? t("settings.planStarter")
                      : plan === "business"
                        ? t("settings.planBusiness")
                        : t("settings.planPro")}
                </Badge>
              </div>
              {plan === "trial" && trialDaysLeft > 0 && (
                <div className="space-y-2">
                  <p className="text-sm text-amber-600 dark:text-amber-500">
                    {t("settings.trialDaysLeft", { count: trialDaysLeft })}
                  </p>
                  <Progress
                    value={Math.max(0, TRIAL_DAYS_TOTAL - trialDaysLeft)}
                    max={TRIAL_DAYS_TOTAL}
                    className="h-2"
                  />
                </div>
              )}
              <div className="space-y-2">
                <p className="text-sm">
                  {t("settings.productsLimit", {
                    current: productsCount,
                    limit: limits.products,
                  })}
                </p>
                <Progress
                  value={productsCount}
                  max={limits.products}
                  variant={productsVariant}
                />
              </div>
              <div className="space-y-2">
                <p className="text-sm">
                  {t("settings.competitorsLimit", {
                    current: competitorsCount,
                    limit: limits.competitors,
                  })}
                </p>
                <Progress
                  value={competitorsCount}
                  max={limits.competitors}
                  variant={competitorsVariant}
                />
              </div>
              <Button className="w-full bg-accent text-accent-foreground hover:bg-accent/90" size="lg">
                <Zap className="mr-2 size-4" />
                {t("settings.upgradePlan")}
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
