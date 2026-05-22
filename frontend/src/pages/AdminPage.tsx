import { useEffect, useMemo, useRef, useState } from "react";
import { useQueryClient } from "@tanstack/react-query";
import { Clock3, Copy, Loader2, Play, Plus } from "lucide-react";
import { toast } from "sonner";
import { PageHeader } from "@/components/ui-custom/PageHeader";
import { EmptyState } from "@/components/ui-custom/EmptyState";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs";
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
import { useAuthStore } from "@/stores/authStore";
import {
  useAddParsingTestMarketplaces,
  useAdminStats,
  useParsingJobStatus,
  useParsingTestMarketplaces,
  useParsingTestRuns,
  useRunParsingFullTest,
} from "@/hooks/useAdmin";

const RUNS_PAGE_SIZE = 20;
const RUNS_LIMIT = 500;

function formatDateTime(value: string | null): string {
  if (!value) return "—";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "—";
  return new Intl.DateTimeFormat("ru-RU", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(date);
}

function formatDuration(seconds: number | null): string {
  if (seconds == null || Number.isNaN(seconds)) return "—";
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

function statusLabel(status: "running" | "completed" | "failed"): string {
  if (status === "completed") return "Успешно";
  if (status === "failed") return "С ошибками";
  return "В процессе";
}

function marketplaceActivityLabel(status: "running" | "completed" | "failed"): string {
  return status === "running" ? "Активен" : "Неактивен";
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
  const queryClient = useQueryClient();
  const user = useAuthStore((state) => state.user);
  const [activeJobId, setActiveJobId] = useState<string | null>(null);
  const [historyPage, setHistoryPage] = useState(1);
  const [detailsJobId, setDetailsJobId] = useState<string | null>(null);
  const [isDetailsOpen, setIsDetailsOpen] = useState(false);
  const previousActiveStatus = useRef<"running" | "completed" | "failed" | null>(null);

  const { data: stats } = useAdminStats();
  const marketplacesQuery = useParsingTestMarketplaces();
  const runsQuery = useParsingTestRuns(RUNS_LIMIT);
  const addMarketplaces = useAddParsingTestMarketplaces();
  const runPipeline = useRunParsingFullTest();

  const activeStatusQuery = useParsingJobStatus(activeJobId, {
    enabled: Boolean(activeJobId),
    refetchInterval: 4500,
  });
  const detailsStatusQuery = useParsingJobStatus(detailsJobId, {
    enabled: isDetailsOpen && Boolean(detailsJobId),
    refetchInterval: isDetailsOpen ? 4500 : false,
  });

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
    const status = activeStatusQuery.data?.status;
    if (!status) return;

    if (previousActiveStatus.current === "running" && (status === "completed" || status === "failed")) {
      const summary = activeStatusQuery.data?.metadata?.summary;
      if (status === "completed") {
        toast.success(
          `Тест завершён: listings ${summary?.listings_created ?? 0}, prices ${summary?.prices_saved ?? 0}, errors ${summary?.errors_count ?? 0}`,
        );
      } else {
        toast.error(
          `Тест завершился с ошибками: listings ${summary?.listings_created ?? 0}, prices ${summary?.prices_saved ?? 0}, errors ${summary?.errors_count ?? 0}`,
        );
      }
      setActiveJobId(null);
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-runs"] });
      queryClient.invalidateQueries({ queryKey: ["admin", "parsing", "test-marketplaces"] });
    }

    previousActiveStatus.current = status;
  }, [activeStatusQuery.data, queryClient]);

  if (!user?.is_superuser) {
    return (
      <div className="space-y-6">
        <PageHeader title="nav.admin" />
        <Card>
          <CardContent className="pt-6">
            <EmptyState
              title="Доступ запрещён"
              description="Раздел администрирования парсинга доступен только superuser-аккаунтам."
            />
          </CardContent>
        </Card>
      </div>
    );
  }

  const activeStatus = activeStatusQuery.data;
  const detailsStatus = detailsStatusQuery.data;
  const currentStage = activeStatus?.current_stage ?? "queued";
  const progress = stageToProgress(currentStage, activeStatus?.status ?? "running");

  return (
    <div className="space-y-6">
      <PageHeader title="nav.admin" />

      <Tabs defaultValue="parsing" className="space-y-4">
        <TabsList>
          <TabsTrigger value="overview">Обзор</TabsTrigger>
          <TabsTrigger value="parsing">Тестовый парсинг</TabsTrigger>
        </TabsList>

        <TabsContent value="overview" className="space-y-4">
          <Card>
            <CardHeader>
              <CardTitle>Системные показатели</CardTitle>
              <CardDescription>
                Краткая сводка superuser-админки. Основной рабочий блок находится во вкладке
                «Тестовый парсинг».
              </CardDescription>
            </CardHeader>
            <CardContent className="grid grid-cols-1 gap-4 md:grid-cols-3">
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Пользователи</p>
                <p className="text-2xl font-semibold">{stats?.users_count ?? stats?.users ?? 0}</p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Маркетплейсы</p>
                <p className="text-2xl font-semibold">
                  {stats?.marketplaces_count ?? stats?.marketplaces ?? 0}
                </p>
              </div>
              <div className="rounded-lg border p-4">
                <p className="text-sm text-muted-foreground">Листинги</p>
                <p className="text-2xl font-semibold">{stats?.total_products_monitored ?? 0}</p>
              </div>
            </CardContent>
          </Card>
        </TabsContent>

        <TabsContent value="parsing" className="space-y-6">
          <Card>
            <CardHeader>
              <CardTitle>Администрирование парсинга</CardTitle>
              <CardDescription>
                Единая точка управления тестовым пулом маркетплейсов и полным циклом
                discovery → scrape → persist.
              </CardDescription>
            </CardHeader>
          </Card>

          <Card>
            <CardHeader className="flex flex-row items-center justify-between space-y-0">
              <div>
                <CardTitle>Тестовые маркетплейсы</CardTitle>
                <CardDescription>
                  Список тестового пула с показателями успешности и последними запусками.
                </CardDescription>
              </div>
              <Button
                onClick={async () => {
                  try {
                    const result = await addMarketplaces.mutateAsync();
                    toast.success(
                      `Обновлено: добавлено ${result.added}, пропущено ${result.skipped}`,
                    );
                  } catch {
                    toast.error("Не удалось добавить тестовые маркетплейсы");
                  }
                }}
                disabled={addMarketplaces.isPending}
              >
                {addMarketplaces.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Plus className="mr-2 size-4" />
                )}
                Добавить 5 тестовых маркетплейсов
              </Button>
            </CardHeader>
            <CardContent>
              {marketplacesQuery.isLoading ? (
                <Skeleton className="h-40 w-full" />
              ) : (marketplacesQuery.data?.length ?? 0) === 0 ? (
                <EmptyState
                  title="Пул тестовых маркетплейсов пуст"
                  description="Добавьте тестовые маркетплейсы, чтобы подготовить пайплайн к запуску."
                />
              ) : (
                <Table>
                  <TableHeader>
                    <TableRow>
                      <TableHead>Маркетплейс</TableHead>
                      <TableHead>URL</TableHead>
                      <TableHead>Товаров в пуле</TableHead>
                      <TableHead>Последний успешный scrape</TableHead>
                      <TableHead>Success rate</TableHead>
                      <TableHead>Последний запуск</TableHead>
                      <TableHead>Статус</TableHead>
                    </TableRow>
                  </TableHeader>
                  <TableBody>
                    {marketplacesQuery.data?.map((item) => (
                      <TableRow key={item.url}>
                        <TableCell className="font-medium">{item.name}</TableCell>
                        <TableCell className="max-w-60 truncate">{item.url}</TableCell>
                        <TableCell>{item.products_in_pool}</TableCell>
                        <TableCell>{formatDateTime(item.last_successful_scrape)}</TableCell>
                        <TableCell>{item.success_rate.toFixed(2)}%</TableCell>
                        <TableCell>{formatDateTime(item.last_run)}</TableCell>
                        <TableCell>
                          <Badge variant={statusBadgeVariant(item.status)}>
                            {marketplaceActivityLabel(item.status)}
                          </Badge>
                        </TableCell>
                      </TableRow>
                    ))}
                  </TableBody>
                </Table>
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader className="space-y-3">
              <CardTitle>Запуск тестового пайплайна</CardTitle>
              <CardDescription>
                Запускает полный цикл для тестового пула и обновляет статус через polling каждые 4–5
                секунд.
              </CardDescription>
              <Button
                className="w-full md:w-auto"
                size="lg"
                onClick={async () => {
                  try {
                    const result = await runPipeline.mutateAsync();
                    previousActiveStatus.current = "running";
                    setActiveJobId(result.job_id);
                    toast.success(`Запуск создан: ${result.job_id}`);
                  } catch (error) {
                    const message =
                      typeof error === "object" &&
                      error &&
                      "response" in error &&
                      (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                        ? (error as { response?: { data?: { detail?: string } } }).response?.data?.detail
                        : "Не удалось запустить полный тест";
                    toast.error(message ?? "Не удалось запустить полный тест");
                  }
                }}
                disabled={runPipeline.isPending || activeStatus?.status === "running"}
              >
                {runPipeline.isPending ? (
                  <Loader2 className="mr-2 size-4 animate-spin" />
                ) : (
                  <Play className="mr-2 size-4" />
                )}
                Запустить полный цикл тестового парсинга
              </Button>
            </CardHeader>
            <CardContent>
              {activeJobId && activeStatus ? (
                <div className="space-y-4 rounded-lg border p-4">
                  <div className="flex flex-wrap items-center gap-2">
                    <Badge variant={statusBadgeVariant(activeStatus.status)}>
                      {statusLabel(activeStatus.status)}
                    </Badge>
                    <span className="text-sm text-muted-foreground">Job ID: {activeStatus.job_id}</span>
                  </div>
                  <Progress value={progress} max={100} />
                  <div className="grid grid-cols-1 gap-2 text-sm text-muted-foreground md:grid-cols-3">
                    <span>Discovery: {currentStage === "discovery" ? "выполняется" : "ожидание"}</span>
                    <span>Scrape: {currentStage === "scrape" ? "выполняется" : "ожидание"}</span>
                    <span>Persist: {currentStage === "persist" ? "выполняется" : "ожидание"}</span>
                  </div>
                  <div className="grid grid-cols-1 gap-2 text-sm md:grid-cols-2">
                    <span>Старт: {formatDateTime(activeStatus.started_at)}</span>
                    <span>Завершение: {formatDateTime(activeStatus.completed_at)}</span>
                  </div>
                </div>
              ) : (
                <EmptyState
                  title="Активный запуск отсутствует"
                  description="Запустите полный цикл, чтобы начать мониторинг этапов в реальном времени."
                />
              )}
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle>История тестовых запусков</CardTitle>
              <CardDescription>
                Таблица оптимизирована для большого объёма записей через постраничный вывод.
              </CardDescription>
            </CardHeader>
            <CardContent className="space-y-4">
              {runsQuery.isLoading ? (
                <Skeleton className="h-56 w-full" />
              ) : sortedRuns.length === 0 ? (
                <EmptyState
                  title="Запусков пока нет"
                  description="После первого запуска тестового цикла здесь появится история."
                />
              ) : (
                <>
                  <Table>
                    <TableHeader>
                      <TableRow>
                        <TableHead>Job ID</TableHead>
                        <TableHead>Начало</TableHead>
                        <TableHead>Завершение</TableHead>
                        <TableHead>Длительность</TableHead>
                        <TableHead>Listings</TableHead>
                        <TableHead>Prices</TableHead>
                        <TableHead>Errors</TableHead>
                        <TableHead>Статус</TableHead>
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
                                toast.success("Job ID скопирован");
                              }}
                            >
                              <Copy className="size-3.5" />
                              {run.job_id.slice(0, 8)}…
                            </button>
                          </TableCell>
                          <TableCell>{formatDateTime(run.started_at)}</TableCell>
                          <TableCell>{formatDateTime(run.completed_at)}</TableCell>
                          <TableCell>{formatDuration(run.duration_seconds)}</TableCell>
                          <TableCell>{run.listings_created}</TableCell>
                          <TableCell>{run.prices_saved}</TableCell>
                          <TableCell>{run.errors_count}</TableCell>
                          <TableCell>
                            <Badge variant={statusBadgeVariant(run.status)}>{statusLabel(run.status)}</Badge>
                          </TableCell>
                        </TableRow>
                      ))}
                    </TableBody>
                  </Table>

                  <div className="flex items-center justify-between">
                    <p className="text-sm text-muted-foreground">
                      Страница {historyPage} из {totalPages}
                    </p>
                    <div className="flex items-center gap-2">
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.max(1, prev - 1))}
                        disabled={historyPage <= 1}
                      >
                        Назад
                      </Button>
                      <Button
                        variant="outline"
                        size="sm"
                        onClick={() => setHistoryPage((prev) => Math.min(totalPages, prev + 1))}
                        disabled={historyPage >= totalPages}
                      >
                        Вперёд
                      </Button>
                    </div>
                  </div>
                </>
              )}
            </CardContent>
          </Card>
        </TabsContent>
      </Tabs>

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
              Детали запуска {detailsStatus?.job_id ? `#${detailsStatus.job_id.slice(0, 8)}` : ""}
            </DialogTitle>
            <DialogDescription>
              Разбивка времени выполнения и статистика по каждому маркетплейсу.
            </DialogDescription>
          </DialogHeader>

          {detailsStatusQuery.isLoading ? (
            <Skeleton className="h-72 w-full" />
          ) : detailsStatus ? (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-3 md:grid-cols-4">
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">Статус</p>
                    <Badge variant={statusBadgeVariant(detailsStatus.status)}>
                      {statusLabel(detailsStatus.status)}
                    </Badge>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">Старт</p>
                    <p className="text-sm">{formatDateTime(detailsStatus.started_at)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">Завершение</p>
                    <p className="text-sm">{formatDateTime(detailsStatus.completed_at)}</p>
                  </CardContent>
                </Card>
                <Card>
                  <CardContent className="pt-4">
                    <p className="text-xs text-muted-foreground">Общее время</p>
                    <p className="text-sm">{formatDuration(detailsStatus.duration_seconds)}</p>
                  </CardContent>
                </Card>
              </div>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">Breakdown времени</CardTitle>
                </CardHeader>
                <CardContent className="grid grid-cols-1 gap-2 text-sm md:grid-cols-4">
                  <div className="rounded border p-2">
                    Discovery: {detailsStatus.metadata?.timings?.discovery_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    Scrape: {detailsStatus.metadata?.timings?.scrape_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    Persist: {detailsStatus.metadata?.timings?.persist_ms ?? 0} ms
                  </div>
                  <div className="rounded border p-2">
                    Total: {detailsStatus.metadata?.timings?.total_ms ?? 0} ms
                  </div>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle className="text-base">По маркетплейсам</CardTitle>
                </CardHeader>
                <CardContent>
                  {(detailsStatus.metadata?.per_marketplace?.length ?? 0) === 0 ? (
                    <p className="text-sm text-muted-foreground">Детализация по маркетплейсам отсутствует.</p>
                  ) : (
                    <Table>
                      <TableHeader>
                        <TableRow>
                          <TableHead>Маркетплейс</TableHead>
                          <TableHead>Listings</TableHead>
                          <TableHead>Prices</TableHead>
                          <TableHead>Errors</TableHead>
                          <TableHead>Success rate</TableHead>
                          <TableHead>Статус</TableHead>
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
                                <Badge variant={statusBadgeVariant(row.status)}>{statusLabel(row.status)}</Badge>
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
              title="Данные запуска недоступны"
              description="Не удалось загрузить детали выбранного запуска."
            />
          )}
          <DialogFooter>
            <Button variant="outline" onClick={() => setIsDetailsOpen(false)}>
              Закрыть
            </Button>
            <Button
              onClick={async () => {
                try {
                  const result = await runPipeline.mutateAsync();
                  previousActiveStatus.current = "running";
                  setActiveJobId(result.job_id);
                  setIsDetailsOpen(false);
                  toast.success(`Повторный запуск создан: ${result.job_id}`);
                } catch {
                  toast.error("Не удалось запустить повторный тест");
                }
              }}
              disabled={runPipeline.isPending}
            >
              {runPipeline.isPending ? (
                <Loader2 className="mr-2 size-4 animate-spin" />
              ) : (
                <Clock3 className="mr-2 size-4" />
              )}
              Повторить запуск
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>
    </div>
  );
}
