// @vitest-environment happy-dom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { getPipelineStatus } from "@/api/pipeline";
import { usePipelineStatus } from "./usePipelineStatus";

vi.mock("@/api/pipeline", () => ({
  getPipelineStatus: vi.fn(),
}));

function wrapper({ children }: { children: React.ReactNode }) {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false } },
  });
  return <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>;
}

describe("usePipelineStatus", () => {
  it("fetches pipeline status from /admin/parsing/pipeline-status", async () => {
    vi.mocked(getPipelineStatus).mockResolvedValue({
      data: {
        job_id: "job-1",
        status: "running",
        current_stage: "discovery",
        started_at: "2026-06-06T10:00:00Z",
        completed_at: null,
        duration_seconds: 42,
        metadata: null,
        discovery: { done: 2, total: 5, current_domain: "barbora.lv" },
      },
      status: 200,
      statusText: "OK",
      headers: {},
      config: {} as never,
    });

    const { result } = renderHook(() => usePipelineStatus({ refetchInterval: false }), {
      wrapper,
    });

    await waitFor(() => {
      expect(result.current.isSuccess).toBe(true);
    });

    expect(getPipelineStatus).toHaveBeenCalled();
    expect(result.current.data?.status).toBe("running");
    expect(result.current.data?.discovery?.current_domain).toBe("barbora.lv");
  });
});
