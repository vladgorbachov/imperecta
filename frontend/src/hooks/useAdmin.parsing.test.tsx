// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import {
  useAddParsingTestMarketplaces,
  useParsingJobStatus,
  useParsingTestMarketplaces,
  useParsingTestRuns,
  useRunParsingFullTest,
} from "./useAdmin";
import * as adminApi from "@/api/admin";

vi.mock("@/api/admin", () => ({
  getParsingTestMarketplaces: vi.fn(),
  addParsingTestMarketplaces: vi.fn(),
  runParsingFullTest: vi.fn(),
  getParsingTestRuns: vi.fn(),
  getParsingJobStatus: vi.fn(),
}));

vi.mock("@/api/markets", () => ({
  marketsApi: {
    triggerIngest: vi.fn(),
  },
  marketsQueryKeys: {
    all: ["markets"],
    refreshMetadata: () => ["markets", "refresh-metadata"],
  },
}));

function createWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useAdmin parsing hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads test marketplaces", async () => {
    vi.mocked(adminApi.getParsingTestMarketplaces).mockResolvedValue({
      data: [{ name: "Test", url: "https://example.com" }],
    } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useParsingTestMarketplaces(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual([{ name: "Test", url: "https://example.com" }]);
    });
    expect(adminApi.getParsingTestMarketplaces).toHaveBeenCalledTimes(1);
  });

  it("invalidates marketplace query after add mutation", async () => {
    vi.mocked(adminApi.addParsingTestMarketplaces).mockResolvedValue({
      data: { added: 5, skipped: 0 },
    } as never);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useAddParsingTestMarketplaces(), {
      wrapper: createWrapper(queryClient),
    });

    await result.current.mutateAsync();

    expect(adminApi.addParsingTestMarketplaces).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["admin", "parsing", "test-marketplaces"],
    });
  });

  it("loads test runs with limit", async () => {
    vi.mocked(adminApi.getParsingTestRuns).mockResolvedValue({
      data: [{ job_id: "job-1" }],
    } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useParsingTestRuns(100), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toEqual([{ job_id: "job-1" }]);
    });
    expect(adminApi.getParsingTestRuns).toHaveBeenCalledWith(100);
  });

  it("loads job status only when enabled", async () => {
    vi.mocked(adminApi.getParsingJobStatus).mockResolvedValue({
      data: { job_id: "job-active", status: "running" },
    } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(
      () => useParsingJobStatus("job-active", { enabled: true, refetchInterval: false }),
      {
        wrapper: createWrapper(queryClient),
      },
    );

    await waitFor(() => {
      expect(result.current.data).toEqual({ job_id: "job-active", status: "running" });
    });
    expect(adminApi.getParsingJobStatus).toHaveBeenCalledWith("job-active");
  });

  it("runs full test and invalidates runs query", async () => {
    vi.mocked(adminApi.runParsingFullTest).mockResolvedValue({
      data: { job_id: "new-job-id" },
    } as never);
    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");

    const { result } = renderHook(() => useRunParsingFullTest(), {
      wrapper: createWrapper(queryClient),
    });

    await result.current.mutateAsync();

    expect(adminApi.runParsingFullTest).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).toHaveBeenCalledWith({
      queryKey: ["admin", "parsing", "test-runs"],
    });
  });
});
