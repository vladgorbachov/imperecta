import { useQuery } from "@tanstack/react-query";
import { getPipelineStatus } from "@/api/pipeline";

export const pipelineStatusQueryKey = ["pipeline", "status"] as const;

export interface UsePipelineStatusOptions {
  enabled?: boolean;
  refetchInterval?: number | false;
}

/** Polls GET /pipeline-status for the current data-collection pipeline state. */
export function usePipelineStatus(options?: UsePipelineStatusOptions) {
  return useQuery({
    queryKey: pipelineStatusQueryKey,
    queryFn: () => getPipelineStatus().then((response) => response.data),
    enabled: options?.enabled ?? true,
    refetchInterval: options?.refetchInterval ?? 5000,
    staleTime: 0,
  });
}
