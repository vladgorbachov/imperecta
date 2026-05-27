import { useEffect, useMemo, useRef, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  CheckCircle2,
  Clock3,
  Copy,
  Gauge,
  KeyRound,
  Loader2,
  Pencil,
  Play,
  Plus,
  Search,
  Shield,
  Timer,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Line,
  LineChart,
  Pie,
  PieChart,
  ResponsiveContainer,
  ReferenceLine,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
import { Input } from "@/components/ui/input";
import { Switch } from "@/components/ui/switch";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import { Progress } from "@/components/ui/progress";
import { authApi } from "@/api/auth";
import { useAuthStore } from "@/stores/authStore";
import type { ParsingDetailedUser } from "@/api/admin";
import {
  useParsingActiveJob,
  useAdminStats,
  useCreateAdminUser,
  useDeleteAdminUser,
  useParsingJobLiveFeed,
  useParsingMarketplacesDetailed,
  useParsingJobStatus,
  useParsingTestRuns,
  useParsingUsersDetailed,
  useResetAdminUserPassword,
  useRunParsingFullTest,
  useSetAdminUserRole,
  useSetAdminUserStatus,
  useUpdateAdminUser,
} from "@/hooks/useAdmin";

const RUNS_PAGE_SIZE = 20;
const RUNS_LIMIT = 500;
const MARKET_OVERVIEW_COUNT_OPTIONS = [5, 10, 20, 50, 100, 1000] as const;
const DEFAULT_MARKET_OVERVIEW_INITIAL_VISIBLE = 5;
const DEFAULT_MARKET_OVERVIEW_EXPAND_STEP = 20;
const USER_PLAN_OPTIONS = ["trial", "starter", "business", "pro", "enterprise"] as const;
const USER_LANGUAGE_OPTIONS = ["en", "ar", "es", "zh", "ru", "fr", "ro", "uk"] as const;

type UserPlan = (typeof USER_PLAN_OPTIONS)[number];
type UserLanguage = (typeof USER_LANGUAGE_OPTIONS)[number];

interface UserFormState {
  email: string;
  password: string;
  name: string;
  company_name: string;
  plan: UserPlan;
  language: UserLanguage;
  timezone: string;
  is_active: boolean;
  is_superuser: boolean;
}

const DEFAULT_USER_FORM: UserFormState = {
  email: "",
  password: "",
  name: "",
  company_name: "",
  plan: "trial",
  language: "en",
  timezone: "UTC",
  is_active: true,
  is_superuser: false,
};

function extractErrorMessage(error: unknown, fallback: string): string {
  if (
    typeof error === "object" &&
    error &&
    "response" in error &&
    typeof (error as { response?: { data?: { detail?: unknown } } }).response?.data?.detail === "string"
  ) {
    return (error as { response?: { data?: { detail?: string } } }).response?.data?.detail ?? fallback;
  }
  if (error instanceof Error && error.message) return error.message;
  return fallback;
}

function parsePreferredCount(
  value: unknown,
  fallback: (typeof MARKET_OVERVIEW_COUNT_OPTIONS)[number],
): (typeof MARKET_OVERVIEW_COUNT_OPTIONS)[number] {
  const numeric = typeof value === "number" ? value : Number(value);
  if (Number.isInteger(numeric) && MARKET_OVERVIEW_COUNT_OPTIONS.includes(numeric as never)) {
    return numeric as (typeof MARKET_OVERVIEW_COUNT_OPTIONS)[number];
  }
  return fallback;
}

function formatDateTime(value: string | null, locale: string, fallback: string): string {
  if (!value) return fallback;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return fallback;
  return new Intl.DateTimeFormat(locale, {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatDuration(seconds: number | null, fallback: string): string {
  if (seconds == null || Number.isNaN(seconds)) return fallback;
  const total = Math.max(0, Math.floor(seconds));
  const mm = Math.floor(total / 60)
    .toString()
    .padStart(2, "0");
  const ss = (total % 60).toString().padStart(2, "0");
  return `${mm}:${ss}`;
}

function statusBadgeVariant(status: "running" | "completed" | "failed") {
  if (status === "completed") return "default";
  if (status === "failed") return "destructive";
  return "secondary";
}

function statusLabelKey(status: "running" | "completed" | "failed"): string {
  if (status === "completed") return "admin.marketplaces.status.success";
  if (status === "failed") return "admin.marketplaces.status.error";
  return "common.loading";
}

function stageToProgress(stage: string | null, status: "running" | "completed" | "failed"): number {
  if (status === "completed") return 100;
  if (status === "failed") return 100;
  if (!stage) return 5;
  if (stage === "queued") return 10;
  if (stage === "discovery") return 35;
  if (stage === "scrape") return 70;
  if (stage === "persist") return 90;
  return 15;
}

export function AdminPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const setUser = useAuthStore((state) => state.setUser);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [liveJobId, setLiveJobId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [detailsJobId, setDetailsJobId] = useState<string | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const [userSearch, setUserSearch] = useState("");
  const [userPlanFilter, setUserPlanFilter] = useState<string>("all");
  const [userStatusFilter, setUserStatusFilter] = useState<"all" | "active" | "inactive">("all");
  const [userRoleFilter, setUserRoleFilter] = useState<"all" | "superuser" | "regular">("all");
  const [isCreateUserOpen, setIsCreateUserOpen] = useState(false);
  const [isEditUserOpen, setIsEditUserOpen] = useState(false);
  const [isResetPasswordOpen, setIsResetPasswordOpen] = useState(false);
  const [selectedUser, setSelectedUser] = useState<ParsingDetailedUser | null>(null);
  const [createUserForm, setCreateUserForm] = useState<UserFormState>(DEFAULT_USER_FORM);
  const [editUserForm, setEditUserForm] = useState<UserFormState>(DEFAULT_USER_FORM);
  const [newPassword, setNewPassword] = useState("");
  const [forcePasswordChange, setForcePasswordChange] = useState(true);
  const [marketOverviewInitialVisible, setMarketOverviewInitialVisible] = useState<number>(
    DEFAULT_MARKET_OVERVIEW_INITIAL_VISIBLE,
  );
  const [marketOverviewExpandStep, setMarketOverviewExpandStep] = useState<number>(
    DEFAULT_MARKET_OVERVIEW_EXPAND_STEP,
  );
  const [marketOverviewVisibleCount, setMarketOverviewVisibleCount] = useState<number>(
    DEFAULT_MARKET_OVERVIEW_INITIAL_VISIBLE,
  );
  const [isSavingOverviewPreferences, setIsSavingOverviewPreferences] = useState(false);
  const previousActiveStatus = useRef<"running" | "completed" | "failed" | null>(null);
  const previousAlertFingerprint = useRef<string>("");

  const { data: stats } = useAdminStats();
  const activeJobQuery = useParsingActiveJob(4500);
  const usersDetailedQuery = useParsingUsersDetailed(1000);
  const marketplacesDetailedQuery = useParsingMarketplacesDetailed(2000);
  const runsQuery = useParsingTestRuns(RUNS_LIMIT);
  const runPipeline = useRunParsingFullTest();
  const createUserMutation = useCreateAdminUser();
  const updateUserMutation = useUpdateAdminUser();
  const setUserStatusMutation = useSetAdminUserStatus();
  const setUserRoleMutation = useSetAdminUserRole();
  const resetPasswordMutation = useResetAdminUserPassword();
  const deleteUserMutation = useDeleteAdminUser();

  const activeStatusQuery = useParsingJobStatus(activeJobId, {
    enabled: Boolean(activeJobId),
    refetchInterval: 4500,
  });
  const detailsStatusQuery = useParsingJobStatus(detailsJobId, {
    enabled: isDetailsOpen && Boolean(detailsJobId),
    refetchInterval: isDetailsOpen ? 4500 : false,
  });
  const liveFeedQuery = useParsingJobLiveFeed(liveJobId, {
    enabled: Boolean(liveJobId),
    refetchInterval: 3000,
    limit: 300,
    offset: 0,
  });

  useEffect(() => {
    const active = activeJobQuery.data?.active_job;
    if (!active || !active.job_id) return;
    setActiveJobId((prev) => prev ?? active.job_id);
    setLiveJobId((prev) => prev ?? active.job_id);
  }, [activeJobQuery.data]);

  const sortedRuns = useMemo(() => {
    const source = runsQuery.data ?? [];
    return [...source].sort((a, b) => {
      const aa = a.started_at ? new Date(a.started_at).getTime() : 0;
      const bb = b.started_at ? new Date(b.started_at).getTime() : 0;
      return bb - aa;
    });
  }, [runsQuery.data]);

  const totalPages = Math.max(1, Math.ceil(sortedRuns.length / RUNS_PAGE_SIZE));
  const pagedRuns = useMemo(() => {
    const safePage = Math.min(Math.max(historyPage, 1), totalPages);
    const start = (safePage - 1) * RUNS_PAGE_SIZE;
    return sortedRuns.slice(start, start + RUNS_PAGE_SIZE);
  }, [historyPage, sortedRuns, totalPages]);

  useEffect(() => {
    setHistoryPage((page) => Math.min(page, totalPages));
  }, [totalPages]);

  useEffect(() => {
    if (activeJobId) {
      setLiveJobId(activeJobId);
      return;
    }
    if (!liveJobId && sortedRuns[0]?.job_id) {
      setLiveJobId(sortedRuns[0].job_id);
    }
  }, [activeJobId, liveJobId, sortedRuns]);

  useEffect(() => {
    const status = activeStatusQuery.data?.status;
    if (!status) return;

    if (previousActiveStatus.current === "running" && (status === "completed" || status === "failed")) {
      const summary = activeStatusQuery.data?.metadata?.summary;
      if (status === "completed") {
        toast.success(
          `${t("admin.marketplaces.products")}: ${summary?.listings_created ?? 0}, ${t("common.price")}: ${summary?.prices_saved ?? 0}, ${t("admin.stats.errors")}: ${summary?.errors_count ?? 0}`,
        );
      } else {
        toast.error(t("admin.markets.refreshError"));
      }
      setActiveJobId(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-runs"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-marketplaces"] });
    }

    previousActiveStatus.current = status;
  }, [activeStatusQuery.data, queryClient, t]);

  const activeStatus = activeStatusQuery.data;
  const detailsStatus = detailsStatusQuery.data;
  const currentStage = activeStatus?.current_stage ?? "queued";
  const progress = stageToProgress(currentStage, activeStatus?.status ?? "running");
  const liveFeed = liveFeedQuery.data;
  const elapsedSeconds = useMemo(() => {
    if (!liveFeed?.started_at) return null;
    const start = new Date(liveFeed.started_at).getTime();
    if (Number.isNaN(start)) return null;
    const end = liveFeed.completed_at ? new Date(liveFeed.completed_at).getTime() : Date.now();
    if (Number.isNaN(end) || end < start) return null;
    return (end - start) / 1000;
  }, [liveFeed?.started_at, liveFeed?.completed_at]);
  const statusPieData = useMemo(
    () =>
      Object.entries(liveFeed?.status_counts ?? {}).map(([name, value]) => ({
        name,
        value,
      })),
    [liveFeed?.status_counts],
  );
  const stepsByMarketplace = useMemo(() => {
    const grouped = new Map<string, { success: number; failed: number }>();
    for (const step of liveFeed?.steps ?? []) {
      const key = step.marketplace_domain || step.marketplace_id.slice(0, 8);
      const existing = grouped.get(key) ?? { success: 0, failed: 0 };
      if (step.status === "success") {
        existing.success += 1;
      } else {
        existing.failed += 1;
      }
      grouped.set(key, existing);
    }
    return Array.from(grouped.entries()).map(([marketplace, values]) => ({
      marketplace,
      ...values,
    }));
  }, [liveFeed?.steps]);
  const throughputTimeline = useMemo(() => {
    const bucket = new Map<string, { minuteLabel: string; steps: number; success: number; failed: number }>();
    for (const step of liveFeed?.steps ?? []) {
      if (!step.created_at) continue;
      const ts = new Date(step.created_at);
      if (Number.isNaN(ts.getTime())) continue;
      const minuteKey = `${ts.getUTCFullYear()}-${String(ts.getUTCMonth() + 1).padStart(2, "0")}-${String(ts.getUTCDate()).padStart(2, "0")} ${String(ts.getUTCHours()).padStart(2, "0")}:${String(ts.getUTCMinutes()).padStart(2, "0")}`;
      const row = bucket.get(minuteKey) ?? {
        minuteLabel: `${String(ts.getHours()).padStart(2, "0")}:${String(ts.getMinutes()).padStart(2, "0")}`,
        steps: 0,
        success: 0,
        failed: 0,
      };
      row.steps += 1;
      if (step.status === "success") {
        row.success += 1;
      } else {
        row.failed += 1;
      }
      bucket.set(minuteKey, row);
    }
    return Array.from(bucket.entries())
      .sort((a, b) => a[0].localeCompare(b[0]))
      .map(([, value]) => value);
  }, [liveFeed?.steps]);
  const ratePerMinute = useMemo(() => {
    if (!throughputTimeline.length) return 0;
    const total = throughputTimeline.reduce((sum, row) => sum + row.steps, 0);
    return total / throughputTimeline.length;
  }, [throughputTimeline]);
  const etaForecast = useMemo(() => {
    if (!liveFeed) return null;
    const estimatedTotal = liveFeed.estimated_total_steps ?? liveFeed.total_steps;
    const processed = liveFeed.total_steps;
    const remaining = Math.max(0, estimatedTotal - processed);
    if (remaining === 0 || processed === 0) {
      return {
        estimatedTotal,
        remaining,
        avgSeconds: 0,
        bestSeconds: 0,
        worstSeconds: 0,
      };
    }

    const averageRatePerMinute = Math.max(ratePerMinute, 0.1);
    const recentWindow = throughputTimeline.slice(-3);
    const recentRatePerMinute = recentWindow.length
      ? recentWindow.reduce((sum, row) => sum + row.steps, 0) / recentWindow.length
      : averageRatePerMinute;

    const bestRatePerMinute = Math.max(averageRatePerMinute * 1.25, recentRatePerMinute * 1.15, 0.2);
    const worstRatePerMinute = Math.max(Math.min(averageRatePerMinute * 0.65, recentRatePerMinute * 0.75), 0.05);

    const avgSeconds = (remaining * 60) / averageRatePerMinute;
    const bestSeconds = (remaining * 60) / bestRatePerMinute;
    const worstSeconds = (remaining * 60) / worstRatePerMinute;

    return {
      estimatedTotal,
      remaining,
      avgSeconds,
      bestSeconds,
      worstSeconds,
    };
  }, [liveFeed, ratePerMinute, throughputTimeline]);
  const qualityAlerts = useMemo(() => {
    if (!liveFeed || liveFeed.total_steps === 0) return [];
    const total = liveFeed.total_steps;
    const missingCritical = liveFeed.status_counts.missing_critical_data ?? 0;
    const technicalError = liveFeed.status_counts.technical_error ?? 0;
    const success = liveFeed.status_counts.success ?? 0;
    const missingCriticalRate = missingCritical / total;
    const technicalErrorRate = technicalError / total;
    const successRate = success / total;
    const rateLimitSteps = (liveFeed.steps ?? []).filter((step) =>
      (step.error_message ?? "").toLowerCase().includes("rate_limit")
      || (step.error_message ?? "").toLowerCase().includes("429")
    ).length;
    const rateLimitRate = rateLimitSteps / total;

    const alerts: Array<{ level: "warning" | "error"; code: string; message: string }> = [];
    if (missingCriticalRate >= 0.2) {
      alerts.push({
        level: "warning",
        code: "missing_critical_high",
        message: `High missing critical data: ${(missingCriticalRate * 100).toFixed(1)}%`,
      });
    }
    if (technicalErrorRate >= 0.1) {
      alerts.push({
        level: "error",
        code: "technical_error_high",
        message: `High technical errors: ${(technicalErrorRate * 100).toFixed(1)}%`,
      });
    }
    if (rateLimitRate >= 0.15) {
      alerts.push({
        level: "warning",
        code: "rate_limit_high",
        message: `High rate-limit pressure: ${(rateLimitRate * 100).toFixed(1)}%`,
      });
    }
    if (successRate < 0.55 && total >= 20) {
      alerts.push({
        level: "error",
        code: "success_rate_low",
        message: `Low success rate: ${(successRate * 100).toFixed(1)}%`,
      });
    }
    return alerts;
  }, [liveFeed]);

  useEffect(() => {
    if (!qualityAlerts.length) {
      previousAlertFingerprint.current = "";
      return;
    }
    const fingerprint = qualityAlerts.map((alert) => `${alert.code}:${alert.message}`).join("|");
    if (previousAlertFingerprint.current === fingerprint) return;
    previousAlertFingerprint.current = fingerprint;
    const critical = qualityAlerts.find((alert) => alert.level === "error");
    if (critical) {
      toast.error(critical.message);
      return;
    }
    toast.warning(qualityAlerts[0].message);
  }, [qualityAlerts]);

  useEffect(() => {
    const preferences =
      user && typeof user.preferences === "object" && user.preferences
        ? (user.preferences as Record<string, unknown>)
        : null;
    const adminUi =
      preferences && typeof preferences.admin_ui === "object" && preferences.admin_ui
        ? (preferences.admin_ui as Record<string, unknown>)
        : null;
    const marketOverview =
      adminUi && typeof adminUi.market_overview === "object" && adminUi.market_overview
        ? (adminUi.market_overview as Record<string, unknown>)
        : null;

    const initialVisible = parsePreferredCount(
      marketOverview?.initial_visible_count,
      DEFAULT_MARKET_OVERVIEW_INITIAL_VISIBLE,
    );
    const expandStep = parsePreferredCount(
      marketOverview?.expand_step_count,
      DEFAULT_MARKET_OVERVIEW_EXPAND_STEP,
    );

    setMarketOverviewInitialVisible(initialVisible);
    setMarketOverviewExpandStep(expandStep);
    setMarketOverviewVisibleCount(initialVisible);
  }, [user]);

  const persistMarketOverviewPreferences = async (patch: {
    initial_visible_count?: number;
    expand_step_count?: number;
  }) => {
    if (!user) return;
    const basePreferences =
      user.preferences && typeof user.preferences === "object"
        ? (user.preferences as Record<string, unknown>)
        : {};
    const baseAdminUi =
      basePreferences.admin_ui && typeof basePreferences.admin_ui === "object"
        ? (basePreferences.admin_ui as Record<string, unknown>)
        : {};
    const baseMarketOverview =
      baseAdminUi.market_overview && typeof baseAdminUi.market_overview === "object"
        ? (baseAdminUi.market_overview as Record<string, unknown>)
        : {};

    const nextPreferences: Record<string, unknown> = {
      ...basePreferences,
      admin_ui: {
        ...baseAdminUi,
        market_overview: {
          ...baseMarketOverview,
          ...patch,
        },
      },
    };

    setIsSavingOverviewPreferences(true);
    try {
      const { data } = await authApi.updateMe({ preferences: nextPreferences });
      setUser(data);
      queryClient.invalidateQueries({ queryKey: ["user", "me"] });
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to save Market Overview preferences"));
    } finally {
      setIsSavingOverviewPreferences(false);
    }
  };

  const allMarketOverviewItems = useMemo(() => marketplacesDetailedQuery.data ?? [], [marketplacesDetailedQuery.data]);
  const visibleMarketOverviewItems = useMemo(
    () => allMarketOverviewItems.slice(0, marketOverviewVisibleCount),
    [allMarketOverviewItems, marketOverviewVisibleCount],
  );
  const hasMoreMarketOverviewItems = marketOverviewVisibleCount < allMarketOverviewItems.length;

  const usersRows = useMemo(() => usersDetailedQuery.data ?? [], [usersDetailedQuery.data]);
  const usersSummary = useMemo(() => {
    const total = usersRows.length;
    const active = usersRows.filter((row) => row.is_active).length;
    const superusers = usersRows.filter((row) => row.is_superuser).length;
    const trial = usersRows.filter((row) => row.plan === "trial").length;
    return { total, active, superusers, trial };
  }, [usersRows]);

  const filteredUsers = useMemo(() => {
    const query = userSearch.trim().toLowerCase();
    return usersRows.filter((row) => {
      const matchesSearch =
        !query ||
        row.email.toLowerCase().includes(query) ||
        (row.name ?? "").toLowerCase().includes(query) ||
        (row.company_name ?? "").toLowerCase().includes(query);
      const matchesPlan = userPlanFilter === "all" || row.plan === userPlanFilter;
      const matchesStatus =
        userStatusFilter === "all" ||
        (userStatusFilter === "active" ? row.is_active : !row.is_active);
      const matchesRole =
        userRoleFilter === "all" ||
        (userRoleFilter === "superuser" ? row.is_superuser : !row.is_superuser);
      return matchesSearch && matchesPlan && matchesStatus && matchesRole;
    });
  }, [usersRows, userSearch, userPlanFilter, userStatusFilter, userRoleFilter]);

  const usersMutationsBusy =
    createUserMutation.isPending ||
    updateUserMutation.isPending ||
    setUserStatusMutation.isPending ||
    setUserRoleMutation.isPending ||
    resetPasswordMutation.isPending ||
    deleteUserMutation.isPending;

  const mapUserToForm = (userRow: ParsingDetailedUser): UserFormState => ({
    email: userRow.email,
    password: "",
    name: userRow.name ?? "",
    company_name: userRow.company_name ?? "",
    plan: (USER_PLAN_OPTIONS.includes(userRow.plan as UserPlan) ? userRow.plan : "trial") as UserPlan,
    language: (USER_LANGUAGE_OPTIONS.includes(userRow.language as UserLanguage)
      ? userRow.language
      : "en") as UserLanguage,
    timezone: userRow.timezone || "UTC",
    is_active: userRow.is_active,
    is_superuser: userRow.is_superuser,
  });

  const onCreateUser = async () => {
    try {
      await createUserMutation.mutateAsync({
        email: createUserForm.email.trim(),
        password: createUserForm.password,
        name: createUserForm.name.trim() || null,
        company_name: createUserForm.company_name.trim() || null,
        plan: createUserForm.plan,
        language: createUserForm.language,
        timezone: createUserForm.timezone.trim() || "UTC",
        is_active: createUserForm.is_active,
        is_superuser: createUserForm.is_superuser,
      });
      toast.success("User created");
      setCreateUserForm(DEFAULT_USER_FORM);
      setIsCreateUserOpen(false);
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to create user"));
    }
  };

  const onUpdateUser = async () => {
    if (!selectedUser) return;
    try {
      await updateUserMutation.mutateAsync({
        userId: selectedUser.id,
        payload: {
          email: editUserForm.email.trim(),
          name: editUserForm.name.trim() || null,
          company_name: editUserForm.company_name.trim() || null,
          plan: editUserForm.plan,
          language: editUserForm.language,
          timezone: editUserForm.timezone.trim() || "UTC",
          is_active: editUserForm.is_active,
          is_superuser: editUserForm.is_superuser,
        },
      });
      toast.success("User updated");
      setIsEditUserOpen(false);
      setSelectedUser(null);
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to update user"));
    }
  };

  const onResetPassword = async () => {
    if (!selectedUser) return;
    try {
      await resetPasswordMutation.mutateAsync({
        userId: selectedUser.id,
        new_password: newPassword,
        force_password_change: forcePasswordChange,
      });
      toast.success("Password reset");
      setNewPassword("");
      setForcePasswordChange(true);
      setIsResetPasswordOpen(false);
      setSelectedUser(null);
    } catch (error) {
      toast.error(extractErrorMessage(error, "Failed to reset password"));
    }
  };

  if (!user?.is_superuser) {
    return (
      <div className="space-y-6">
        <PageHeader title="nav.admin" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title={t("common.error")}
              description={t("admin.markets.refreshError")}
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader title="nav.admin" />

      <Tabs defaultValue="data-collection" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Market Overview</TabsTrigger>
          <TabsTrigger value="data-collection">Data Collection</TabsTrigger>
          <TabsTrigger value="users-management">Users Management</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>{t("admin.title")}</CardTitle>
              <CardDescription>{t("admin.stats.scrapesToday")}</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.stats.users")}</p>
                <p className="text-2xl font-semibold">{stats?.users_count ?? stats?.users ?? 0}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.stats.marketplaces")}</p>
                <p className="text-2xl font-semibold">{stats?.marketplaces_count ?? stats?.marketplaces ?? 0}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">{t("admin.marketplaces.products")}</p>
                <p className="text-2xl font-semibold">{stats?.total_products_monitored ?? 0}</p>
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>{t("admin.pool.marketplaces")}</CardTitle>
                <CardDescription>{t("admin.marketplaces.successRate")}</CardDescription>
              </div>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded border p-3">
                <div className="text-sm text-muted-foreground">
                  Показано {Math.min(marketOverviewVisibleCount, allMarketOverviewItems.length)} из{" "}
                  {allMarketOverviewItems.length}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Старт</span>
                    <Select
                      value={String(marketOverviewInitialVisible)}
                      onValueChange={async (value) => {
                        const count = Number(value);
                        setMarketOverviewInitialVisible(count);
                        setMarketOverviewVisibleCount(count);
                        await persistMarketOverviewPreferences({ initial_visible_count: count });
                      }}
                    >
                      <SelectTrigger className="w-[92px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {MARKET_OVERVIEW_COUNT_OPTIONS.map((count) => (
                          <SelectItem key={`overview-initial-${count}`} value={String(count)}>
                            {count}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  <div className="flex items-center gap-2">
                    <span className="text-xs text-muted-foreground">Шаг</span>
                    <Select
                      value={String(marketOverviewExpandStep)}
                      onValueChange={async (value) => {
                        const count = Number(value);
                        setMarketOverviewExpandStep(count);
                        await persistMarketOverviewPreferences({ expand_step_count: count });
                      }}
                    >
                      <SelectTrigger className="w-[92px]">
                        <SelectValue />
                      </SelectTrigger>
                      <SelectContent>
                        {MARKET_OVERVIEW_COUNT_OPTIONS.map((count) => (
                          <SelectItem key={`overview-step-${count}`} value={String(count)}>
                            {count}
                          </SelectItem>
                        ))}
                      </SelectContent>
                    </Select>
                  </div>
                  {hasMoreMarketOverviewItems ? (
                    <Button
                      variant="outline"
                      onClick={() =>
                        setMarketOverviewVisibleCount((prev) =>
                          Math.min(allMarketOverviewItems.length, prev + marketOverviewExpandStep),
                        )
                      }
                    >
                      <ChevronDown className="mr-2 size-4" />
                      Развернуть (+{marketOverviewExpandStep})
                    </Button>
                  ) : null}
                  {isSavingOverviewPreferences ? (
                    <Badge variant="secondary">
                      <Loader2 className="mr-1 size-3 animate-spin" />
                      saving
                    </Badge>
                  ) : null}
                </div>
              </div>
              {marketplacesDetailedQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (marketplacesDetailedQuery.data?.length ?? 0) === 0 ? (
                <EmptyState title={t("common.noData")} description={t("admin.pool.marketplaces")} />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>{t("products.marketplace")}</TableHead>
                      <TableHead>{t("competitors.tableUrl")}</TableHead>
                      <TableHead>{t("admin.pool.productsInPool")}</TableHead>
                      <TableHead>Active listings</TableHead>
                      <TableHead>{t("admin.marketplaces.lastScrape")}</TableHead>
                      <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                      <TableHead>{t("admin.markets.lastRefresh")}</TableHead>
                      <TableHead>{t("common.status")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {visibleMarketOverviewItems.map((item) => (
                      <TableRow key={item.id}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="max-w-60 truncate">{item.base_url}</TableCell>
                        <TableCell>{item.products_in_pool}</TableCell>
                        <TableCell>{item.active_listings}</TableCell>
                        <TableCell>{formatDateTime(item.last_scrape_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{item.success_rate.toFixed(2)}%</TableCell>
                        <TableCell>{formatDateTime(item.last_discovery_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>
                          <Badge variant={item.is_active ? "default" : "destructive"}>
                            {item.is_active ? "active" : "inactive"}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="data-collection" className="space-y-6">
          <Card>
            <CardHeader className="space-y-3">
              <CardTitle>Data Collection</CardTitle>
              <CardDescription>
                Полный live-контроль сбора данных: стадии, ошибки, темп, прогноз и шаги в реальном времени.
              </CardDescription>
              <div className="flex flex-wrap items-center gap-3">
                <Button
                  className="w-full md:w-auto"
                  size="lg"
                  onClick={async () => {
                    try {
                      const result = await runPipeline.mutateAsync();
                      previousActiveStatus.current = "running";
                      setActiveJobId(result.job_id);
                      setLiveJobId(result.job_id);
                      toast.success(`${t("common.save")}: ${result.job_id}`);
                    } catch (error) {
                      const message =
                        typeof error === "object" &&
                        error &&
                        "response" in error &&
                        (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                          ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                          : t("admin.markets.refreshError");
                      toast.error(message ?? t("admin.markets.refreshError"));
                    }
                  }}
                  disabled={runPipeline.isPending || activeStatus?.status === "running"}
                >
                  {runPipeline.isPending ? (
                    <Loader2 className="mr-2 size-4 animate-spin" />
                  ) : (
                    <Play className="mr-2 size-4" />
                  )}
                  Run Data Collection
                </Button>
                {activeStatus && (
                  <Badge variant={statusBadgeVariant(activeStatus.status)}>
                    {t(statusLabelKey(activeStatus.status))}
                  </Badge>
                )}
                {activeStatus?.job_id && (
                  <span className="text-sm text-muted-foreground">{activeStatus.job_id}</span>
                )}
              </div>
            </CardHeader>
            <CardContent className="space-y-4">
              <Progress value={progress} max={100} />
              <div className="grid grid-cols-1 gap-3 text-sm md:grid-cols-3">
                <div className="rounded border p-3">{t("admin.pool.triggerDiscovery")}: {currentStage === "discovery" ? t("common.loading") : t("common.noData")}</div>
                <div className="rounded border p-3">{t("admin.pool.triggerScraping")}: {currentStage === "scrape" ? t("common.loading") : t("common.noData")}</div>
                <div className="rounded border p-3">{t("admin.pool.diagnostics")}: {currentStage === "persist" ? t("common.loading") : t("common.noData")}</div>
              </div>
              {liveFeed?.warning_flags?.length ? (
                <div className="flex flex-col gap-2 rounded border border-amber-500/40 bg-amber-500/5 p-3 text-sm">
                  <div className="flex items-center gap-2 font-medium text-amber-700 dark:text-amber-300">
                    <AlertTriangle className="size-4" />
                    Обнаружены риски качества данных
                  </div>
                  {liveFeed.warning_flags.map((flag) => (
                    <span key={flag}>- {flag}</span>
                  ))}
                </div>
              ) : null}
              {qualityAlerts.length ? (
                <div className="flex flex-col gap-2 rounded border border-red-500/40 bg-red-500/5 p-3 text-sm">
                  <div className="flex items-center gap-2 font-medium text-red-700 dark:text-red-300">
                    <AlertTriangle className="size-4" />
                    Аномалии процесса сбора данных
                  </div>
                  {qualityAlerts.map((alert) => (
                    <div key={alert.code} className="flex items-center gap-2">
                      <Badge variant={alert.level === "error" ? "destructive" : "secondary"}>
                        {alert.level.toUpperCase()}
                      </Badge>
                      <span>{alert.message}</span>
                    </div>
                  ))}
                </div>
              ) : null}
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Elapsed</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Timer className="size-5 text-primary" />
                  {formatDuration(elapsedSeconds, t("common.dash"))}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Processed steps</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Gauge className="size-5 text-primary" />
                  {liveFeed?.total_steps ?? 0}
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">Success rate</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <CheckCircle2 className="size-5 text-emerald-500" />
                  {liveFeed?.total_steps ? (((liveFeed.status_counts.success ?? 0) / liveFeed.total_steps) * 100).toFixed(1) : "0.0"}%
                </p>
              </CardContent>
            </Card>
            <Card>
              <CardContent className="pt-4">
                <p className="text-xs text-muted-foreground">ETA (avg)</p>
                <p className="mt-1 flex items-center gap-2 text-2xl font-semibold">
                  <Clock3 className="size-5 text-primary" />
                  {formatDuration(etaForecast?.avgSeconds ?? liveFeed?.estimated_remaining_seconds ?? null, t("common.dash"))}
                </p>
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Forecast window</CardTitle>
              <CardDescription>Прогноз завершения на основе фактической скорости обработки.</CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Best ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.bestSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Average ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.avgSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3">
                <p className="text-xs text-muted-foreground">Worst ETA</p>
                <p className="text-lg font-semibold">{formatDuration(etaForecast?.worstSeconds ?? null, t("common.dash"))}</p>
              </div>
              <div className="rounded border p-3 md:col-span-3">
                <p className="text-xs text-muted-foreground">Scope</p>
                <p className="text-sm">
                  processed {liveFeed?.total_steps ?? 0}
                  {etaForecast?.estimatedTotal ? ` / estimated ${etaForecast.estimatedTotal}` : ""}
                  {etaForecast?.remaining ? `, remaining ${etaForecast.remaining}` : ""}
                </p>
              </div>
            </CardContent>
          </Card>

          <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
            <Card>
              <CardHeader>
                <CardTitle>Status distribution</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {statusPieData.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Status distribution" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <PieChart>
                      <Pie data={statusPieData} dataKey="value" nameKey="name" outerRadius={100} label>
                        {statusPieData.map((entry, idx) => (
                          <Cell
                            key={`${entry.name}-${idx}`}
                            fill={entry.name === "success" ? "#16a34a" : entry.name === "missing_critical_data" ? "#f59e0b" : "#ef4444"}
                          />
                        ))}
                      </Pie>
                      <Tooltip />
                    </PieChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Marketplace performance</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {stepsByMarketplace.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Marketplace performance" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <BarChart data={stepsByMarketplace}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="marketplace" />
                      <YAxis />
                      <Tooltip />
                      <Bar dataKey="success" stackId="a" fill="#16a34a" />
                      <Bar dataKey="failed" stackId="a" fill="#ef4444" />
                    </BarChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>

            <Card>
              <CardHeader>
                <CardTitle>Throughput timeline</CardTitle>
              </CardHeader>
              <CardContent className="h-72">
                {throughputTimeline.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Throughput timeline" />
                ) : (
                  <ResponsiveContainer width="100%" height="100%">
                    <LineChart data={throughputTimeline}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="minuteLabel" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      <ReferenceLine y={ratePerMinute} stroke="#6366f1" strokeDasharray="4 4" />
                      <Line type="monotone" dataKey="steps" stroke="#0ea5e9" strokeWidth={2} dot={false} name="steps/min" />
                      <Line type="monotone" dataKey="success" stroke="#16a34a" strokeWidth={2} dot={false} name="success/min" />
                      <Line type="monotone" dataKey="failed" stroke="#ef4444" strokeWidth={2} dot={false} name="failed/min" />
                    </LineChart>
                  </ResponsiveContainer>
                )}
              </CardContent>
            </Card>
          </div>

          <Card>
            <CardHeader>
              <CardTitle>Live process log</CardTitle>
              <CardDescription>Каждая операция по листингу отображается в реальном времени.</CardDescription>
            </CardHeader>
            <CardContent>
              {liveFeedQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : !liveFeed ? (
                <EmptyState title={t("common.noData")} description="Live process log" />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Time</TableHead>
                      <TableHead>Marketplace</TableHead>
                      <TableHead>Status</TableHead>
                      <TableHead>Duration</TableHead>
                      <TableHead>Price</TableHead>
                      <TableHead>URL</TableHead>
                      <TableHead>Error</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {liveFeed.steps.map((step) => (
                      <TableRow key={step.event_id}>
                        <TableCell>{formatDateTime(step.created_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                        <TableCell>{step.marketplace_domain || step.marketplace_id.slice(0, 8)}</TableCell>
                        <TableCell>
                          <Badge variant={step.status === "success" ? "default" : "secondary"}>{step.status}</Badge>
                        </TableCell>
                        <TableCell>{step.duration_ms ?? t("common.dash")}</TableCell>
                        <TableCell>{step.price_found ?? t("common.dash")}</TableCell>
                        <TableCell className="max-w-72 truncate">{step.url}</TableCell>
                        <TableCell className="max-w-80 truncate">{step.error_message || t("common.dash")}</TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>{t("admin.pool.discoveryLogs")}</CardTitle>
              <CardDescription>{t("admin.pool.diagnosticsResult")}</CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {runsQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : sortedRuns.length === 0 ? (
                <EmptyState title={t("common.noData")} description={t("admin.pool.discoveryLogs")} />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>{t("admin.pool.diagnostics")}</TableHead>
                        <TableHead>{t("alerts.date")}</TableHead>
                        <TableHead>{t("admin.markets.lastRefresh")}</TableHead>
                        <TableHead>{t("admin.claude.avgLatency")}</TableHead>
                        <TableHead>{t("admin.marketplaces.products")}</TableHead>
                        <TableHead>{t("common.price")}</TableHead>
                        <TableHead>{t("admin.stats.errors")}</TableHead>
                        <TableHead>{t("common.status")}</TableHead>
                        <TableHead>Live</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {pagedRuns.map((run) => (
                        <TableRow
                          key={run.job_id}
                          className="cursor-pointer"
                          onClick={() => {
                            setDetailsJobId(run.job_id);
                            setIsDetailsOpen(true);
                          }}
                        >
                          <TableCell>
                            <button
                              type="button"
                              className="inline-flex items-center gap-2 text-left text-sm text-primary hover:underline"
                              onClick={(event) => {
                                event.stopPropagation();
                                navigator.clipboard.writeText(run.job_id);
                                toast.success(t("common.copied"));
                              }}
                            >
                              <Copy className="size-3.5" />
                              {run.job_id.slice(0, 8)}…
                            </button>
                          </TableCell>
                          <TableCell>{formatDateTime(run.started_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                          <TableCell>{formatDateTime(run.completed_at, i18n.resolvedLanguage || "en", t("common.dash"))}</TableCell>
                          <TableCell>{formatDuration(run.duration_seconds, t("common.dash"))}</TableCell>
                          <TableCell>{run.listings_created}</TableCell>
                          <TableCell>{run.prices_saved}</TableCell>
                          <TableCell>{run.errors_count}</TableCell>
                          <TableCell>
                            <Badge variant={statusBadgeVariant(run.status)}>
                              {t(statusLabelKey(run.status))}
                            </Badge>
                          </TableCell>
                          <TableCell>
                            <Button
                              variant="outline"
                              size="sm"
                              onClick={(event) => {
                                event.stopPropagation();
                                setLiveJobId(run.job_id);
                                toast.success(`Live feed: ${run.job_id.slice(0, 8)}…`);
                              }}
                            >
                              Watch
                            </Button>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">{historyPage}/{totalPages}</p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                        disabled={historyPage <= 1}
                      >
                        {t("common.back")}
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={historyPage >= totalPages}
                      >
                        {t("common.next")}
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="users-management">
          <div className="space-y-4">
            <Card>
              <CardHeader className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>Users Management</CardTitle>
                    <CardDescription>
                      Расширенное управление пользователями: создание, редактирование, роли, статус, пароль, удаление.
                    </CardDescription>
                  </div>
                  <Button
                    onClick={() => {
                      setCreateUserForm(DEFAULT_USER_FORM);
                      setIsCreateUserOpen(true);
                    }}
                  >
                    <Plus className="mr-2 size-4" />
                    Add user
                  </Button>
                </div>
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="rounded border p-3">
                    <p className="text-xs text-muted-foreground">Total users</p>
                    <p className="text-xl font-semibold">{usersSummary.total}</p>
                  </div>
                  <div className="rounded border p-3">
                    <p className="text-xs text-muted-foreground">Active users</p>
                    <p className="text-xl font-semibold">{usersSummary.active}</p>
                  </div>
                  <div className="rounded border p-3">
                    <p className="text-xs text-muted-foreground">Superusers</p>
                    <p className="text-xl font-semibold">{usersSummary.superusers}</p>
                  </div>
                  <div className="rounded border p-3">
                    <p className="text-xs text-muted-foreground">Trial users</p>
                    <p className="text-xl font-semibold">{usersSummary.trial}</p>
                  </div>
                </div>
              </CardHeader>
              <CardContent className="space-y-3">
                <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                  <div className="relative md:col-span-2">
                    <Search className="pointer-events-none absolute left-3 top-1/2 size-4 -translate-y-1/2 text-muted-foreground" />
                    <Input
                      className="pl-9"
                      placeholder="Search by email/name/company"
                      value={userSearch}
                      onChange={(event) => setUserSearch(event.target.value)}
                    />
                  </div>
                  <Select value={userPlanFilter} onValueChange={setUserPlanFilter}>
                    <SelectTrigger>
                      <SelectValue placeholder="Plan filter" />
                    </SelectTrigger>
                    <SelectContent>
                      <SelectItem value="all">All plans</SelectItem>
                      {USER_PLAN_OPTIONS.map((plan) => (
                        <SelectItem key={plan} value={plan}>
                          {plan}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <div className="grid grid-cols-2 gap-2">
                    <Select
                      value={userStatusFilter}
                      onValueChange={(value) =>
                        setUserStatusFilter(value as "all" | "active" | "inactive")
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Status" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All status</SelectItem>
                        <SelectItem value="active">Active</SelectItem>
                        <SelectItem value="inactive">Inactive</SelectItem>
                      </SelectContent>
                    </Select>
                    <Select
                      value={userRoleFilter}
                      onValueChange={(value) =>
                        setUserRoleFilter(value as "all" | "superuser" | "regular")
                      }
                    >
                      <SelectTrigger>
                        <SelectValue placeholder="Role" />
                      </SelectTrigger>
                      <SelectContent>
                        <SelectItem value="all">All roles</SelectItem>
                        <SelectItem value="superuser">Superuser</SelectItem>
                        <SelectItem value="regular">Regular</SelectItem>
                      </SelectContent>
                    </Select>
                  </div>
                </div>

                {usersDetailedQuery.isLoading ? (
                  <Skeleton className="h-56 w-full" />
                ) : filteredUsers.length === 0 ? (
                  <EmptyState title={t("common.noData")} description="Users Management" />
                ) : (
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>User</TableHead>
                        <TableHead>Plan</TableHead>
                        <TableHead>Language</TableHead>
                        <TableHead>Tracked</TableHead>
                        <TableHead>Logins</TableHead>
                        <TableHead>Last login</TableHead>
                        <TableHead>Created</TableHead>
                        <TableHead>Status</TableHead>
                        <TableHead>Superuser</TableHead>
                        <TableHead>Actions</TableHead>
                      </TableRow>
                    </TableHeader>
                    <TableBody>
                      {filteredUsers.map((userRow) => (
                        <TableRow key={userRow.id}>
                          <TableCell>
                            <div className="space-y-0.5">
                              <p className="font-medium">{userRow.email}</p>
                              <p className="text-xs text-muted-foreground">
                                {userRow.name || t("common.dash")}
                                {userRow.company_name ? ` • ${userRow.company_name}` : ""}
                              </p>
                            </div>
                          </TableCell>
                          <TableCell>
                            <Badge variant="secondary">{userRow.plan}</Badge>
                          </TableCell>
                          <TableCell>{userRow.language}</TableCell>
                          <TableCell>{userRow.tracked_products}</TableCell>
                          <TableCell>{userRow.login_count}</TableCell>
                          <TableCell>
                            {formatDateTime(userRow.last_login_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                          </TableCell>
                          <TableCell>
                            {formatDateTime(userRow.created_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={userRow.is_active}
                                disabled={usersMutationsBusy}
                                onCheckedChange={async (checked) => {
                                  try {
                                    await setUserStatusMutation.mutateAsync({
                                      userId: userRow.id,
                                      is_active: checked,
                                    });
                                    toast.success(`User ${checked ? "activated" : "deactivated"}`);
                                  } catch (error) {
                                    toast.error(extractErrorMessage(error, "Failed to update status"));
                                  }
                                }}
                              />
                              <Badge variant={userRow.is_active ? "default" : "destructive"}>
                                {userRow.is_active ? "active" : "inactive"}
                              </Badge>
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-2">
                              <Switch
                                checked={userRow.is_superuser}
                                disabled={usersMutationsBusy}
                                onCheckedChange={async (checked) => {
                                  try {
                                    await setUserRoleMutation.mutateAsync({
                                      userId: userRow.id,
                                      is_superuser: checked,
                                    });
                                    toast.success(`Role updated: ${checked ? "superuser" : "regular"}`);
                                  } catch (error) {
                                    toast.error(extractErrorMessage(error, "Failed to update role"));
                                  }
                                }}
                              />
                              {userRow.is_superuser ? (
                                <Shield className="size-4 text-primary" />
                              ) : (
                                <span className="text-xs text-muted-foreground">regular</span>
                              )}
                            </div>
                          </TableCell>
                          <TableCell>
                            <div className="flex items-center gap-1">
                              <Button
                                variant="outline"
                                size="icon"
                                onClick={() => {
                                  setSelectedUser(userRow);
                                  setEditUserForm(mapUserToForm(userRow));
                                  setIsEditUserOpen(true);
                                }}
                              >
                                <Pencil className="size-4" />
                              </Button>
                              <Button
                                variant="outline"
                                size="icon"
                                onClick={() => {
                                  setSelectedUser(userRow);
                                  setNewPassword("");
                                  setForcePasswordChange(true);
                                  setIsResetPasswordOpen(true);
                                }}
                              >
                                <KeyRound className="size-4" />
                              </Button>
                              <Button
                                variant="destructive"
                                size="icon"
                                onClick={async () => {
                                  if (
                                    !window.confirm(
                                      `Delete user ${userRow.email}? This operation is permanent.`,
                                    )
                                  ) {
                                    return;
                                  }
                                  try {
                                    await deleteUserMutation.mutateAsync(userRow.id);
                                    toast.success("User deleted");
                                  } catch (error) {
                                    toast.error(extractErrorMessage(error, "Failed to delete user"));
                                  }
                                }}
                              >
                                <Trash2 className="size-4" />
                              </Button>
                            </div>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>
                )}
              </CardContent>
            </Card>
          </div>
        </TabsContent>
      </Tabs>

      <Dialog open={isCreateUserOpen} onOpenChange={setIsCreateUserOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Create user</DialogTitle>
            <DialogDescription>Создание нового пользователя с настройкой роли и плана.</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3">
            <Input
              placeholder="Email"
              value={createUserForm.email}
              onChange={(event) =>
                setCreateUserForm((prev) => ({ ...prev, email: event.target.value }))
              }
            />
            <Input
              placeholder="Temporary password"
              type="password"
              value={createUserForm.password}
              onChange={(event) =>
                setCreateUserForm((prev) => ({ ...prev, password: event.target.value }))
              }
            />
            <Input
              placeholder="Name"
              value={createUserForm.name}
              onChange={(event) =>
                setCreateUserForm((prev) => ({ ...prev, name: event.target.value }))
              }
            />
            <Input
              placeholder="Company"
              value={createUserForm.company_name}
              onChange={(event) =>
                setCreateUserForm((prev) => ({ ...prev, company_name: event.target.value }))
              }
            />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Select
                value={createUserForm.plan}
                onValueChange={(value) =>
                  setCreateUserForm((prev) => ({ ...prev, plan: value as UserPlan }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Plan" />
                </SelectTrigger>
                <SelectContent>
                  {USER_PLAN_OPTIONS.map((plan) => (
                    <SelectItem key={plan} value={plan}>
                      {plan}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={createUserForm.language}
                onValueChange={(value) =>
                  setCreateUserForm((prev) => ({ ...prev, language: value as UserLanguage }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Language" />
                </SelectTrigger>
                <SelectContent>
                  {USER_LANGUAGE_OPTIONS.map((language) => (
                    <SelectItem key={language} value={language}>
                      {language}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                placeholder="Timezone"
                value={createUserForm.timezone}
                onChange={(event) =>
                  setCreateUserForm((prev) => ({ ...prev, timezone: event.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3 rounded border p-3">
              <label className="flex items-center justify-between gap-2 text-sm">
                <span>Active account</span>
                <Switch
                  checked={createUserForm.is_active}
                  onCheckedChange={(checked) =>
                    setCreateUserForm((prev) => ({ ...prev, is_active: checked }))
                  }
                />
              </label>
              <label className="flex items-center justify-between gap-2 text-sm">
                <span>Superuser</span>
                <Switch
                  checked={createUserForm.is_superuser}
                  onCheckedChange={(checked) =>
                    setCreateUserForm((prev) => ({ ...prev, is_superuser: checked }))
                  }
                />
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsCreateUserOpen(false)}>
              {t("common.close")}
            </Button>
            <Button
              onClick={onCreateUser}
              disabled={
                createUserMutation.isPending
                || !createUserForm.email.trim()
                || createUserForm.password.length < 8
              }
            >
              {createUserMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Plus className="mr-2 size-4" />
              )}
              Create
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isEditUserOpen}
        onOpenChange={(open) => {
          setIsEditUserOpen(open);
          if (!open) setSelectedUser(null);
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Edit user</DialogTitle>
            <DialogDescription>{selectedUser?.email ?? t("common.dash")}</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3">
            <Input
              placeholder="Email"
              value={editUserForm.email}
              onChange={(event) =>
                setEditUserForm((prev) => ({ ...prev, email: event.target.value }))
              }
            />
            <Input
              placeholder="Name"
              value={editUserForm.name}
              onChange={(event) =>
                setEditUserForm((prev) => ({ ...prev, name: event.target.value }))
              }
            />
            <Input
              placeholder="Company"
              value={editUserForm.company_name}
              onChange={(event) =>
                setEditUserForm((prev) => ({ ...prev, company_name: event.target.value }))
              }
            />
            <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
              <Select
                value={editUserForm.plan}
                onValueChange={(value) => setEditUserForm((prev) => ({ ...prev, plan: value as UserPlan }))}
              >
                <SelectTrigger>
                  <SelectValue placeholder="Plan" />
                </SelectTrigger>
                <SelectContent>
                  {USER_PLAN_OPTIONS.map((plan) => (
                    <SelectItem key={plan} value={plan}>
                      {plan}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Select
                value={editUserForm.language}
                onValueChange={(value) =>
                  setEditUserForm((prev) => ({ ...prev, language: value as UserLanguage }))
                }
              >
                <SelectTrigger>
                  <SelectValue placeholder="Language" />
                </SelectTrigger>
                <SelectContent>
                  {USER_LANGUAGE_OPTIONS.map((language) => (
                    <SelectItem key={language} value={language}>
                      {language}
                    </SelectItem>
                  ))}
                </SelectContent>
              </Select>
              <Input
                placeholder="Timezone"
                value={editUserForm.timezone}
                onChange={(event) =>
                  setEditUserForm((prev) => ({ ...prev, timezone: event.target.value }))
                }
              />
            </div>
            <div className="grid grid-cols-2 gap-3 rounded border p-3">
              <label className="flex items-center justify-between gap-2 text-sm">
                <span>Active account</span>
                <Switch
                  checked={editUserForm.is_active}
                  onCheckedChange={(checked) =>
                    setEditUserForm((prev) => ({ ...prev, is_active: checked }))
                  }
                />
              </label>
              <label className="flex items-center justify-between gap-2 text-sm">
                <span>Superuser</span>
                <Switch
                  checked={editUserForm.is_superuser}
                  onCheckedChange={(checked) =>
                    setEditUserForm((prev) => ({ ...prev, is_superuser: checked }))
                  }
                />
              </label>
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditUserOpen(false)}>
              {t("common.close")}
            </Button>
            <Button
              onClick={onUpdateUser}
              disabled={updateUserMutation.isPending || !selectedUser || !editUserForm.email.trim()}
            >
              {updateUserMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Pencil className="mr-2 size-4" />
              )}
              Save
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isResetPasswordOpen}
        onOpenChange={(open) => {
          setIsResetPasswordOpen(open);
          if (!open) {
            setSelectedUser(null);
            setNewPassword("");
            setForcePasswordChange(true);
          }
        }}
      >
        <DialogContent>
          <DialogHeader>
            <DialogTitle>Reset password</DialogTitle>
            <DialogDescription>{selectedUser?.email ?? t("common.dash")}</DialogDescription>
          </DialogHeader>
          <div className="grid grid-cols-1 gap-3">
            <Input
              placeholder="New password"
              type="password"
              value={newPassword}
              onChange={(event) => setNewPassword(event.target.value)}
            />
            <label className="flex items-center justify-between rounded border p-3 text-sm">
              <span>Force password change on next login</span>
              <Switch checked={forcePasswordChange} onCheckedChange={setForcePasswordChange} />
            </label>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsResetPasswordOpen(false)}>
              {t("common.close")}
            </Button>
            <Button
              onClick={onResetPassword}
              disabled={resetPasswordMutation.isPending || !selectedUser || newPassword.length < 8}
            >
              {resetPasswordMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <KeyRound className="mr-2 size-4" />
              )}
              Reset
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog
        open={isDetailsOpen}
        onOpenChange={(open) => {
          setIsDetailsOpen(open);
          if (!open) setDetailsJobId(null);
        }}
      >
        <DialogContent className="max-w-4xl">
          <DialogHeader>
            <DialogTitle>
              {t("admin.pool.diagnosticsResult")}{" "}
              {detailsStatus?.job_id ? `#${detailsStatus.job_id.slice(0, 8)}` : ""}
            </DialogTitle>
            <DialogDescription>{t("admin.pool.diagnostics")}</DialogDescription>
          </DialogHeader>

          {detailsStatusQuery.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : detailsStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("common.status")}</p>
                    <Badge variant={statusBadgeVariant(detailsStatus.status)}>
                      {t(statusLabelKey(detailsStatus.status))}
                    </Badge>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("alerts.date")}</p>
                    <p className="text-sm">
                      {formatDateTime(detailsStatus.started_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("admin.markets.lastRefresh")}</p>
                    <p className="text-sm">
                      {formatDateTime(detailsStatus.completed_at, i18n.resolvedLanguage || "en", t("common.dash"))}
                    </p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">{t("admin.claude.avgLatency")}</p>
                    <p className="text-sm">{formatDuration(detailsStatus.duration_seconds, t("common.dash"))}</p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("admin.pool.diagnosticsResult")}</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-2 text-sm md:grid-cols-4">
                  <div className="rounded border p-2">
                    {t("admin.pool.triggerDiscovery")}: {detailsStatus.metadata?.timings?.discovery_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.pool.triggerScraping")}: {detailsStatus.metadata?.timings?.scrape_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.pool.diagnostics")}: {detailsStatus.metadata?.timings?.persist_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    {t("admin.claude.tokens24h")}: {detailsStatus.metadata?.timings?.total_ms ?? 0} ms
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">{t("admin.pool.marketplaces")}</CardTitle>
                </CardHeader>
                <CardContent>
                  {(detailsStatus.metadata?.per_marketplace?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">{t("common.noData")}</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>{t("products.marketplace")}</TableHead>
                          <TableHead>{t("admin.marketplaces.products")}</TableHead>
                          <TableHead>{t("common.price")}</TableHead>
                          <TableHead>{t("admin.stats.errors")}</TableHead>
                          <TableHead>{t("admin.marketplaces.successRate")}</TableHead>
                          <TableHead>{t("common.status")}</TableHead>
                        </TableRow>
                      </TableHeader>
                      <TableBody>
                        {detailsStatus.metadata?.per_marketplace?.map((row) => {
                          const denominator = row.prices_saved + row.errors_count;
                          const rate = denominator > 0 ? (row.prices_saved / denominator) * 100 : 0;
                          return (
                            <TableRow key={`${row.marketplace_id}-${row.domain}`}>
                              <TableCell>{row.domain}</TableCell>
                              <TableCell>{row.listings_created}</TableCell>
                              <TableCell>{row.prices_saved}</TableCell>
                              <TableCell>{row.errors_count}</TableCell>
                              <TableCell>{rate.toFixed(2)}%</TableCell>
                              <TableCell>
                                <Badge variant={statusBadgeVariant(row.status)}>
                                  {t(statusLabelKey(row.status))}
                                </Badge>
                              </TableCell>
                            </TableRow>
                          );
                        })}
                      </TableBody>
                    </Table>
                  )}
                </CardContent>
              </Card>
            </div>
          ) : (
            <EmptyState
              title={t("common.error")}
              description={t("admin.markets.refreshError")}
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              {t("common.close")}
            </Button>
            <Button
              onClick={async () => {
                try {
                  const result = await runPipeline.mutateAsync();
                  previousActiveStatus.current = "running";
                  setActiveJobId(result.job_id);
                  setLiveJobId(result.job_id);
                  setIsDetailsOpen(false);
                  toast.success(`${t("common.refresh")}: ${result.job_id}`);
                } catch {
                  toast.error(t("admin.markets.refreshError"));
                }
              }}
              disabled={runPipeline.isPending}
            >
              {runPipeline.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Clock3 className="mr-2 size-4" />
              )}
              {t("common.refresh")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
