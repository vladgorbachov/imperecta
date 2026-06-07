import type { ParsingDiscoveryProgress, ParsingJobMetadata } from "@/api/admin";
import { apiClient } from "@/api/client";

export type PipelineRunStatus = "idle" | "running" | "completed" | "failed";

/** Response from GET /api/admin/parsing/pipeline-status. */
export interface PipelineStatusResponse {
  job_id: string | null;
  status: PipelineRunStatus;
  current_stage: string | null;
  started_at: string | null;
  completed_at: string | null;
  duration_seconds: number | null;
  metadata: ParsingJobMetadata | null;
  discovery: ParsingDiscoveryProgress | null;
}

export const getPipelineStatus = () =>
  apiClient.get<PipelineStatusResponse>("/admin/parsing/pipeline-status");
