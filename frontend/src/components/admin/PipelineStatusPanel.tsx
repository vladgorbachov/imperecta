import { useMemo } from "react";
import { useTranslation } from "react-i18next";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import type { PipelineStatusResponse } from "@/api/pipeline";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Progress } from "@/components/ui/progress";
import { Skeleton } from "@/components/ui/skeleton";
import { usePipelineStatus } from "@/hooks/usePipelineStatus";
import { cn } from "@/lib/utils";

export interface PipelineStatusPanelProps {
  /** Polling interval in ms; false disables auto-refresh. */
  pollInterval?: number | false;
  enabled?: boolean;
  className?: string;
}

function formatDuration(seconds: number | null, fallback: string): string {
  if (seconds == null || Number.isNaN(seconds)) {
    return fallback;
  }
  const total = Math.max(0, Math.floor(seconds));
  const hours = Math.floor(total / 3600);
  const minutes = Math.floor((total % 3600) / 60)
    .toString()
    .padStart(2, "0");
  const secs = (total % 60).toString().padStart(2, "0");
  if (hours > 0) {
    return `${hours}:${minutes}:${secs}`;
  }
  return `${minutes}:${secs}`;
}

function statusBadgeVariant(status: PipelineStatusResponse["status"]) {
  if (status === "completed") {
    return "outline";
  }
  if (status === "failed") {
    return "destructive";
  }
  if (status === "running") {
    return "secondary";
  }
  return "outline";
}

function statusBadgeClassName(status: PipelineStatusResponse["status"]): string {
  if (status === "completed") {
    return "border-green-500/40 bg-green-500/15 text-green-700 dark:text-green-300";
  }
  if (status === "running") {
    return "border-amber-500/40 bg-amber-500/15 text-amber-800 dark:text-amber-200";
  }
  if (status === "failed") {
    return "";
  }
  return "text-muted-foreground";
}

function statusLabelKey(status: PipelineStatusResponse["status"]): string {
  if (status === "completed") {
    return "admin.dataCollection.stageStatus.completed";
  }
  if (status === "failed") {
    return "admin.dataCollection.stageStatus.failed";
  }
  if (status === "running") {
    return "admin.dataCollection.stageStatus.inProgress";
  }
  return "admin.dataCollection.pipelineIdle";
}

function stageLabelKey(stage: string | null | undefined): string {
  switch (stage) {
    case "dispatching":
      return "admin.dataCollection.stage.dispatching";
    case "discovery":
      return "admin.dataCollection.stage.discovery";
    case "scrape":
      return "admin.dataCollection.stage.scrape";
    case "persist":
      return "admin.dataCollection.stage.persist";
    case "completed":
      return "admin.dataCollection.stage.completed";
    case "failed":
      return "admin.dataCollection.stage.failed";
    case "queued":
      return "admin.dataCollection.stage.queued";
    default:
      return "admin.dataCollection.stage.unknown";
  }
}

function computeProgress(status: PipelineStatusResponse | undefined): number {
  if (!status || status.status !== "running") {
    return status?.status === "completed" ? 100 : 0;
  }
  const discovery = status.discovery;
  if (discovery?.total && discovery.total > 0) {
    return Math.min(100, Math.round((discovery.done / discovery.total) * 100));
  }
  const stage = status.current_stage ?? status.metadata?.current_stage;
  if (stage === "discovery") {
    return 20;
  }
  if (stage === "scrape") {
    return 55;
  }
  if (stage === "persist") {
    return 85;
  }
  return 10;
}

function MetricTile({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-md border p-3 text-sm">
      <p className="text-muted-foreground">{label}</p>
      <p className="font-medium">{value}</p>
    </div>
  );
}

/**
 * Polls GET /pipeline-status and renders the current pipeline run state.
 */
export function PipelineStatusPanel({
  pollInterval = 5000,
  enabled = true,
  className,
}: PipelineStatusPanelProps) {
  const { t } = useTranslation();
  const dash = t("common.dash");
  const query = usePipelineStatus({
    enabled,
    refetchInterval: pollInterval,
  });

  const status = query.data;
  const currentStage = status?.current_stage ?? status?.metadata?.current_stage ?? null;
  const discovery = status?.discovery;
  const summary = status?.metadata?.summary;
  const progress = useMemo(() => computeProgress(status), [status]);

  return (
    <Card className={cn(className)}>
      <CardHeader className="space-y-2">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <CardTitle>{t("admin.dataCollection.liveMonitor")}</CardTitle>
          <div className="flex items-center gap-2">
            {status ? (
              <Badge
                variant={statusBadgeVariant(status.status)}
                className={statusBadgeClassName(status.status)}
              >
                {t(statusLabelKey(status.status))}
              </Badge>
            ) : null}
            <Button
              type="button"
              variant="ghost"
              size="icon"
              className="size-8"
              onClick={() => void query.refetch()}
              disabled={query.isFetching}
              aria-label={t("common.refresh")}
            >
              {query.isFetching ? (
                <Loader2 className="size-4 animate-spin" />
              ) : (
                <RefreshCw className="size-4" />
              )}
            </Button>
          </div>
        </div>
        <CardDescription>
          {status?.status === "idle"
            ? t("admin.dataCollection.pipelineIdle")
            : t(stageLabelKey(currentStage))}
          {discovery?.total
            ? ` · ${t("admin.dataCollection.discoveryProgress", {
                done: discovery.done,
                total: discovery.total,
              })}`
            : ""}
          {discovery?.current_domain ? ` · ${discovery.current_domain}` : ""}
        </CardDescription>
      </CardHeader>

      <CardContent className="space-y-4">
        {query.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : query.isError ? (
          <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 p-3 text-sm text-destructive">
            <AlertTriangle className="size-4 shrink-0" />
            {t("admin.dataCollection.pipelineStatusError")}
          </div>
        ) : status?.status === "idle" ? (
          <p className="text-sm text-muted-foreground">
            {t("admin.dataCollection.pipelineIdle")}
          </p>
        ) : (
          <>
            <Progress value={progress} max={100} />
            <div className="grid grid-cols-2 gap-3 md:grid-cols-4">
              <MetricTile
                label={t("admin.dataCollection.metric.stage")}
                value={t(stageLabelKey(currentStage))}
              />
              <MetricTile
                label={t("admin.marketplaces.products")}
                value={String(summary?.listings_created ?? 0)}
              />
              <MetricTile
                label={t("common.price")}
                value={String(summary?.prices_saved ?? 0)}
              />
              <MetricTile
                label={t("admin.stats.errors")}
                value={String(summary?.errors_count ?? 0)}
              />
              <MetricTile
                label={t("admin.dataCollection.metric.elapsed")}
                value={formatDuration(status?.duration_seconds ?? null, dash)}
              />
              {status?.job_id ? (
                <MetricTile label="Job ID" value={status.job_id.slice(0, 8)} />
              ) : null}
            </div>
            {status?.metadata?.error ? (
              <p className="rounded-md border border-destructive/30 bg-destructive/10 p-3 text-sm text-destructive">
                {status.metadata.error}
              </p>
            ) : null}
          </>
        )}
      </CardContent>
    </Card>
  );
}
