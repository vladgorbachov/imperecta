// MOBILE-2026: fully responsive + bottom nav + drawer

/**
 * Settings page: Profile, Telegram, Notifications, AI Personalization, Plan sections.
 * Sections separated by shadcn Separator.
 *
 * i18n keys used:
 * - nav.settings, settings.*, auth.*, common.*
 */

import { useState, useEffect, useRef } from "react";
import { useTranslation } from "react-i18next";
import { Copy, Zap, Upload, Link as LinkIcon } from "lucide-react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { authApi } from "@/api/auth";
import { analyticsApi } from "@/api/analytics";
import { useAuthStore } from "@/stores/authStore";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle, CardDescription } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { LanguageSelector } from "@/components/ui/LanguageSelector";
import type { LanguageCode } from "@/i18n";
import { RadioGroup, RadioGroupItemStyled } from "@/components/ui/radio-group";
import { Progress } from "@/components/ui/progress";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { Skeleton } from "@/components/ui/skeleton";
import { Avatar, AvatarFallback, AvatarImage } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import { toast } from "sonner";

const BOT_USERNAME = "@ImperectaBot";
const BOT_URL = "https://t.me/ImperectaBot";
const CODE_DURATION_SEC = 300;
function getPlanLimits(plan: string): { products: number; competitors: number } {
  switch (plan) {
    case "trial": return { products: 999, competitors: 999 };
    case "starter": return { products: 50, competitors: 15 };
    case "business": return { products: 100, competitors: 30 };
    case "pro": return { products: 999, competitors: 999 };
    default: return { products: 999, competitors: 999 };
  }
}

const TRIAL_DAYS_TOTAL = 14;

const AVATAR_MAX_SIZE_BYTES = 2 * 1024 * 1024; // 2MB

function isValidAvatarUrl(url: string): boolean {
  const trimmed = url.trim();
  return trimmed.startsWith("http://") || trimmed.startsWith("https://");
}

export function SettingsPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const setUser = useAuthStore((s) => s.setUser);
  const updateLanguage = useAuthStore((s) => s.updateLanguage);

  const [profileForm, setProfileForm] = useState({ name: "", company_name: "" });
  const [avatarUrl, setAvatarUrl] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);
  const [telegramCode, setTelegramCode] = useState<string | null>(null);
  const [codeSecondsLeft, setCodeSecondsLeft] = useState(0);
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
  const isAdmin = u?.is_superuser ?? false;

  useEffect(() => {
    if (u) {
      setProfileForm({ name: u.name, company_name: u.company_name ?? "" });
      setAvatarUrl((u as { avatar_url?: string | null }).avatar_url ?? "");
      const tone = (u as { ai_tone?: string }).ai_tone;
      if (tone && ["conservative", "balanced", "aggressive"].includes(tone)) {
        setDigestTone(tone as "conservative" | "balanced" | "aggressive");
      }
    }
  }, [u]);

  useEffect(() => {
    if (telegramCode && codeSecondsLeft > 0) {
      const id = setInterval(() => setCodeSecondsLeft((s) => Math.max(0, s - 1)), 1000);
      return () => clearInterval(id);
    }
  }, [telegramCode, codeSecondsLeft]);

  const updateMutation = useMutation({
    mutationFn: async (data: {
      name?: string;
      company_name?: string;
      language?: string;
      avatar_url?: string | null;
      ai_tone?: string;
    }) => {
      const res = await authApi.updateMe(data);
      return res.data;
    },
    onSuccess: (updatedUser) => {
      if (updatedUser) setUser(updatedUser);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      toast.success(t("auth.profileUpdated"));
    },
    onError: (err: unknown) => {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string | unknown[] } } }).response?.data?.detail
          : null;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail.length > 0
            ? String((detail[0] as { msg?: string })?.msg ?? detail[0])
            : null;
      toast.error(msg ?? t("auth.updateFailed"));
    },
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
    onError: (err: unknown) => {
      const detail =
        err && typeof err === "object" && "response" in err
          ? (err as { response?: { data?: { detail?: string | unknown[] } } }).response?.data?.detail
          : null;
      const msg =
        typeof detail === "string"
          ? detail
          : Array.isArray(detail) && detail.length > 0
            ? String((detail[0] as { msg?: string })?.msg ?? detail[0])
            : null;
      toast.error(msg ?? t("auth.updateFailed"));
    },
  });

  const handleProfileSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    updateMutation.mutate({
      name: profileForm.name,
      company_name: profileForm.company_name || undefined,
      avatar_url: avatarUrl.trim() || null,
    });
  };

  const handleSaveAvatarUrl = () => {
    const url = avatarUrl.trim();
    if (!url) return;
    if (!isValidAvatarUrl(url)) {
      toast.error(t("settings.avatar.invalidUrl"));
      return;
    }
    updateMutation.mutate({ avatar_url: url });
  };

  const handleDeleteAvatar = () => {
    if (!window.confirm(t("settings.avatar.deleteConfirm"))) return;
    authApi.deleteAvatar().then(async () => {
      setAvatarUrl("");
      const { data } = await authApi.getMe();
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
      toast.success(t("settings.avatar.deleted"));
    }).catch(() => {
      updateMutation.mutate({ avatar_url: "" });
    });
  };

  const handleFileSelect = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    if (!file.type.startsWith("image/")) {
      toast.error(t("settings.avatar.invalidType"));
      return;
    }
    if (file.size > AVATAR_MAX_SIZE_BYTES) {
      toast.error(t("settings.avatar.maxSize"));
      return;
    }
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result as string;
      if (result.startsWith("data:image/")) {
        setAvatarUrl(result);
      }
    };
    reader.readAsDataURL(file);
    e.target.value = "";
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
  const limits = getPlanLimits(plan);
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
    <div className="mx-auto w-full max-w-2xl space-y-6 px-0 sm:px-0">
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
                  <label className="text-sm font-medium">{t("settings.avatar")}</label>
                  <div className="flex flex-col gap-4 sm:flex-row sm:flex-wrap sm:items-start">
                    <Avatar className="size-16 shrink-0">
                      <AvatarImage src={avatarUrl || undefined} alt={u?.name} />
                      <AvatarFallback className="bg-primary/20 text-primary">
                        {u?.name
                          ?.split(" ")
                          .map((n) => n[0])
                          .join("")
                          .toUpperCase()
                          .slice(0, 2) ?? "?"}
                      </AvatarFallback>
                    </Avatar>
                    <div className="flex flex-col gap-2">
                      <div className="flex flex-wrap gap-2">
                        <input
                          ref={fileInputRef}
                          type="file"
                          accept="image/*"
                          className="hidden"
                          onChange={handleFileSelect}
                        />
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={() => fileInputRef.current?.click()}
                        >
                          <Upload className="me-2 size-4" />
                          {t("settings.avatar.upload")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          onClick={handleSaveAvatarUrl}
                          disabled={updateMutation.isPending || !avatarUrl.trim()}
                        >
                          <LinkIcon className="me-2 size-4" />
                          {t("common.save")}
                        </Button>
                        <Button
                          type="button"
                          variant="outline"
                          size="sm"
                          className="border-destructive/50 text-destructive hover:bg-destructive/10"
                          onClick={handleDeleteAvatar}
                        >
                          {t("settings.avatar.delete")}
                        </Button>
                      </div>
                      <div className="flex items-center gap-2">
                        <Input
                          placeholder={t("settings.avatar.urlPlaceholder")}
                          value={avatarUrl.startsWith("data:") ? "" : avatarUrl}
                          onChange={(e) => setAvatarUrl(e.target.value)}
                          className="w-full max-w-xs sm:max-w-xs"
                        />
                        <span className="text-xs text-muted-foreground">
                          {t("settings.avatar.maxSize")}
                        </span>
                      </div>
                    </div>
                  </div>
                </div>
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
                  <Input
                    value={u?.email ?? ""}
                    disabled
                    className="flex-1 bg-muted dark:bg-muted"
                  />
                </div>
                <div className="space-y-2">
                  <label className="text-sm font-medium">{t("auth.language")}</label>
                  <LanguageSelector
                    value={(u?.language as LanguageCode) ?? (i18n.language as LanguageCode)}
                    onChange={handleLanguageChange}
                    showFlags
                    compact={false}
                    isAdmin={isAdmin}
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
            <CardContent>
              <p className="text-sm text-muted-foreground dark:text-muted-foreground">
                {t("settings.digestTimeComingSoon")}
              </p>
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
              <Button
                type="button"
                onClick={() => updateMutation.mutate({ ai_tone: digestTone })}
                disabled={updateMutation.isPending}
              >
                {updateMutation.isPending ? t("common.loading") : t("common.save")}
              </Button>
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
                      "bg-[var(--color-promo-bg)] text-[var(--color-promo)] border-[var(--color-promo-border)]",
                    plan === "starter" &&
                      "bg-[var(--accent-bg)] text-[var(--accent)] border-[var(--accent-border)]",
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
                  <p className="text-sm" style={{ color: "var(--color-promo)" }}>
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
              <Button
                className="w-full bg-accent text-accent-foreground hover:bg-accent/90"
                size="lg"
                disabled
              >
                <Zap className="mr-2 size-4" />
                {t("settings.upgradeComingSoon")}
              </Button>
            </CardContent>
          </Card>
        </>
      )}
    </div>
  );
}
