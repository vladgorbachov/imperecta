import { useMemo, useState } from "react";
import { useTranslation } from "react-i18next";
import { useQueryClient } from "@tanstack/react-query";
import {
  KeyRound,
  Loader2,
  Pencil,
  Plus,
  Search,
  Shield,
  Trash2,
} from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { DataCollectionTab } from "@/components/admin/DataCollectionTab";
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
import { useAuthStore } from "@/stores/authStore";
import type { ParsingDetailedMarketplace, ParsingDetailedUser } from "@/api/admin";
import {
  useAddMarketplace,
  useAdminStats,
  useCreateAdminUser,
  useDeleteAdminUser,
  useDeleteMarketplace,
  useParsingMarketplacesDetailed,
  useParsingJobStatus,
  useParsingUsersDetailed,
  useResetAdminUserPassword,
  useSetAdminUserRole,
  useSetAdminUserStatus,
  useUpdateAdminUser,
  useUpdateMarketplace,
} from "@/hooks/useAdmin";
const MARKET_OVERVIEW_PAGE_SIZE_OPTIONS = [20, 50, 100] as const;
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

export function AdminPage() {
  const { t, i18n } = useTranslation();
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
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
  const [marketplacePage, setMarketplacePage] = useState(1);
  const [marketplacePageSize, setMarketplacePageSize] = useState<number>(20);
  const [isAddMarketplaceOpen, setIsAddMarketplaceOpen] = useState(false);
  const [isEditMarketplaceOpen, setIsEditMarketplaceOpen] = useState(false);
  const [isDeleteMarketplaceOpen, setIsDeleteMarketplaceOpen] = useState(false);
  const [selectedMarketplace, setSelectedMarketplace] = useState<ParsingDetailedMarketplace | null>(null);
  const [newMarketplaceUrl, setNewMarketplaceUrl] = useState("");
  const [editMarketplaceForm, setEditMarketplaceForm] = useState({ name: "", url: "" });
  const { data: stats } = useAdminStats();
  const usersDetailedQuery = useParsingUsersDetailed(1000);
  const marketplacesDetailedQuery = useParsingMarketplacesDetailed(marketplacePage, marketplacePageSize);
  const addMarketplaceMutation = useAddMarketplace();
  const updateMarketplaceMutation = useUpdateMarketplace();
  const deleteMarketplaceMutation = useDeleteMarketplace();
  const createUserMutation = useCreateAdminUser();
  const updateUserMutation = useUpdateAdminUser();
  const setUserStatusMutation = useSetAdminUserStatus();
  const setUserRoleMutation = useSetAdminUserRole();
  const resetPasswordMutation = useResetAdminUserPassword();
  const deleteUserMutation = useDeleteAdminUser();

  const detailsStatusQuery = useParsingJobStatus(detailsJobId, {
    enabled: isDetailsOpen && Boolean(detailsJobId),
    refetchInterval: isDetailsOpen ? 4500 : false,
  });

  const detailsStatus = detailsStatusQuery.data;

  const marketOverviewItems = marketplacesDetailedQuery.data?.items ?? [];
  const marketOverviewTotal = marketplacesDetailedQuery.data?.total ?? 0;
  const marketOverviewTotalPages = Math.max(1, Math.ceil(marketOverviewTotal / marketplacePageSize));

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
              <Button onClick={() => setIsAddMarketplaceOpen(true)}>
                <Plus className="mr-2 size-4" />
                {t("admin.marketOverview.addMarketplace")}
              </Button>
            </CardHeader>
            <CardContent className="space-y-3">
              <div className="flex flex-wrap items-center justify-between gap-3 rounded border p-3">
                <div className="text-sm text-muted-foreground">
                  {t("admin.marketOverview.showing", {
                    count: marketOverviewItems.length,
                    total: marketOverviewTotal,
                  })}
                </div>
                <div className="flex flex-wrap items-center gap-2">
                  <span className="text-xs text-muted-foreground">{t("admin.marketOverview.pageSize")}</span>
                  <Select
                    value={String(marketplacePageSize)}
                    onValueChange={(value) => {
                      setMarketplacePageSize(Number(value));
                      setMarketplacePage(1);
                    }}
                  >
                    <SelectTrigger className="w-[92px]">
                      <SelectValue />
                    </SelectTrigger>
                    <SelectContent>
                      {MARKET_OVERVIEW_PAGE_SIZE_OPTIONS.map((count) => (
                        <SelectItem key={`overview-page-size-${count}`} value={String(count)}>
                          {count}
                        </SelectItem>
                      ))}
                    </SelectContent>
                  </Select>
                  <span className="text-sm text-muted-foreground">
                    {t("admin.marketOverview.page", {
                      page: marketplacePage,
                      total: marketOverviewTotalPages,
                    })}
                  </span>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={marketplacePage <= 1}
                    onClick={() => setMarketplacePage((page) => Math.max(1, page - 1))}
                  >
                    {t("common.back")}
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    disabled={marketplacePage >= marketOverviewTotalPages}
                    onClick={() =>
                      setMarketplacePage((page) => Math.min(marketOverviewTotalPages, page + 1))
                    }
                  >
                    {t("common.next")}
                  </Button>
                </div>
              </div>
              {marketplacesDetailedQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : marketOverviewItems.length === 0 ? (
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
                      <TableHead className="text-right">{t("common.actions")}</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {marketOverviewItems.map((item) => (
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
                        <TableCell className="text-right">
                          <div className="flex justify-end gap-1">
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              aria-label={t("common.edit")}
                              onClick={() => {
                                setSelectedMarketplace(item);
                                setEditMarketplaceForm({ name: item.name, url: item.base_url });
                                setIsEditMarketplaceOpen(true);
                              }}
                            >
                              <Pencil className="size-4" />
                            </Button>
                            <Button
                              type="button"
                              variant="ghost"
                              size="icon"
                              aria-label={t("common.delete")}
                              onClick={() => {
                                setSelectedMarketplace(item);
                                setIsDeleteMarketplaceOpen(true);
                              }}
                            >
                              <Trash2 className="size-4 text-destructive" />
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
        </TabsContent>

        <TabsContent value="data-collection">
          <DataCollectionTab
            onOpenRunDetails={(jobId) => {
              setDetailsJobId(jobId);
              setIsDetailsOpen(true);
            }}
          />
        </TabsContent>

        <TabsContent value="users-management">
          <div className="space-y-4">
            <Card>
              <CardHeader className="space-y-3">
                <div className="flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <CardTitle>Users Management</CardTitle>
                    <CardDescription>{t("admin.users.managementDescription")}</CardDescription>
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
            <DialogDescription>{t("admin.users.createDescription")}</DialogDescription>
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
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isAddMarketplaceOpen} onOpenChange={setIsAddMarketplaceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.marketOverview.addMarketplace")}</DialogTitle>
            <DialogDescription>{t("admin.marketOverview.addMarketplaceHint")}</DialogDescription>
          </DialogHeader>
          <Input
            value={newMarketplaceUrl}
            onChange={(event) => setNewMarketplaceUrl(event.target.value)}
            placeholder="https://example.com"
          />
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsAddMarketplaceOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={addMarketplaceMutation.isPending || !newMarketplaceUrl.trim()}
              onClick={() => {
                void (async () => {
                  try {
                    await addMarketplaceMutation.mutateAsync(newMarketplaceUrl.trim());
                    toast.success(t("admin.marketOverview.added"));
                    setNewMarketplaceUrl("");
                    setIsAddMarketplaceOpen(false);
                    await queryClient.invalidateQueries({
                      queryKey: ["admin", "parsing", "marketplaces-detailed"],
                    });
                  } catch (error) {
                    toast.error(extractErrorMessage(error, t("admin.marketOverview.addFailed")));
                  }
                })();
              }}
            >
              {addMarketplaceMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : null}
              {t("common.add")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isEditMarketplaceOpen} onOpenChange={setIsEditMarketplaceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.marketOverview.editMarketplace")}</DialogTitle>
            <DialogDescription>{selectedMarketplace?.domain}</DialogDescription>
          </DialogHeader>
          <div className="space-y-3">
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground">{t("products.marketplace")}</label>
              <Input
                value={editMarketplaceForm.name}
                onChange={(event) =>
                  setEditMarketplaceForm((prev) => ({ ...prev, name: event.target.value }))
                }
              />
            </div>
            <div className="space-y-1">
              <label className="text-sm text-muted-foreground">{t("competitors.tableUrl")}</label>
              <Input
                value={editMarketplaceForm.url}
                onChange={(event) =>
                  setEditMarketplaceForm((prev) => ({ ...prev, url: event.target.value }))
                }
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsEditMarketplaceOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              disabled={updateMarketplaceMutation.isPending || !selectedMarketplace}
              onClick={() => {
                if (!selectedMarketplace) return;
                void (async () => {
                  try {
                    await updateMarketplaceMutation.mutateAsync({
                      id: selectedMarketplace.id,
                      payload: {
                        name: editMarketplaceForm.name.trim(),
                        url: editMarketplaceForm.url.trim(),
                      },
                    });
                    toast.success(t("admin.marketOverview.updated"));
                    setIsEditMarketplaceOpen(false);
                    await queryClient.invalidateQueries({
                      queryKey: ["admin", "parsing", "marketplaces-detailed"],
                    });
                  } catch (error) {
                    toast.error(extractErrorMessage(error, t("admin.marketOverview.updateFailed")));
                  }
                })();
              }}
            >
              {updateMarketplaceMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : null}
              {t("common.save")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      <Dialog open={isDeleteMarketplaceOpen} onOpenChange={setIsDeleteMarketplaceOpen}>
        <DialogContent>
          <DialogHeader>
            <DialogTitle>{t("admin.marketOverview.deleteMarketplace")}</DialogTitle>
            <DialogDescription>
              {t("admin.marketOverview.deleteConfirm", {
                name: selectedMarketplace?.name ?? "",
              })}
            </DialogDescription>
          </DialogHeader>
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDeleteMarketplaceOpen(false)}>
              {t("common.cancel")}
            </Button>
            <Button
              variant="destructive"
              disabled={deleteMarketplaceMutation.isPending || !selectedMarketplace}
              onClick={() => {
                if (!selectedMarketplace) return;
                void (async () => {
                  try {
                    await deleteMarketplaceMutation.mutateAsync(selectedMarketplace.id);
                    toast.success(t("admin.marketOverview.deleted"));
                    setIsDeleteMarketplaceOpen(false);
                    if (marketOverviewItems.length === 1 && marketplacePage > 1) {
                      setMarketplacePage((page) => page - 1);
                    }
                    await queryClient.invalidateQueries({
                      queryKey: ["admin", "parsing", "marketplaces-detailed"],
                    });
                  } catch (error) {
                    toast.error(extractErrorMessage(error, t("admin.marketOverview.deleteFailed")));
                  }
                })();
              }}
            >
              {deleteMarketplaceMutation.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : null}
              {t("common.delete")}
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
