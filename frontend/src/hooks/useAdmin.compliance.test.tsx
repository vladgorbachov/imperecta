// @vitest-environment happy-dom

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { act, renderHook, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const api = vi.hoisted(() => ({
  getBlockedCountries: vi.fn(),
  getAvailableCountries: vi.fn(),
  addBlockedCountry: vi.fn(),
  dryRunBlockedCountry: vi.fn(),
  updateBlockedCountry: vi.fn(),
  removeBlockedCountry: vi.fn(),
  completeBlockedCountriesReview: vi.fn(),
  getBlockedCountriesAudit: vi.fn(),
  checkIpCountry: vi.fn(),
}));

/* The hooks are exercised for real; only the HTTP layer is stubbed (no msw
   in the toolchain — the API module is the contract boundary). */
vi.mock("@/api/admin", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/admin")>()),
  ...api,
}));

import {
  useAddBlockedCountry,
  useBlockedCountries,
  useBlockedCountriesAudit,
  useCompleteReview,
  useDryRunBlockedCountry,
  useRemoveBlockedCountry,
} from "./useAdmin";

const blockedRow = {
  country_code: "RU",
  name: "Russia",
  reason: "product_exclusion",
  basis: "EU Reg. 833/2014",
  note: null,
  is_active: true,
  added_by: null,
  added_at: "2026-09-19T00:00:00Z",
  updated_at: "2026-09-19T00:00:00Z",
  review_due_at: "2026-12-18",
  is_protected: false,
  affected_users: 0,
  affected_marketplaces: 0,
};

function createWrapper() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  const invalidateSpy = vi.spyOn(queryClient, "invalidateQueries");
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>{children}</QueryClientProvider>
  );
  return { wrapper, invalidateSpy };
}

describe("compliance hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
    api.getBlockedCountries.mockResolvedValue({
      data: { items: [blockedRow], last_reviewed_at: null, next_review_due_at: "2026-12-18" },
    });
    api.addBlockedCountry.mockResolvedValue({ data: blockedRow });
    api.dryRunBlockedCountry.mockResolvedValue({
      data: { affected_users: 3, affected_marketplaces: 0 },
    });
    api.removeBlockedCountry.mockResolvedValue({});
    api.completeBlockedCountriesReview.mockResolvedValue({
      data: { last_reviewed_at: "2026-09-19", next_review_due_at: "2026-12-18" },
    });
    api.getBlockedCountriesAudit.mockResolvedValue({ data: { items: [], next_cursor: null } });
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("useBlockedCountries returns the list envelope", async () => {
    const { wrapper } = createWrapper();
    const { result } = renderHook(() => useBlockedCountries(), { wrapper });
    await waitFor(() => expect(result.current.isSuccess).toBe(true));
    expect(result.current.data?.items[0].country_code).toBe("RU");
    expect(result.current.data?.next_review_due_at).toBe("2026-12-18");
  });

  it("useAddBlockedCountry posts the payload and invalidates admin queries", async () => {
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useAddBlockedCountry(), { wrapper });
    await act(async () => {
      await result.current.mutateAsync({
        country_code: "IR",
        reason: "comprehensive_sanctions",
        basis: "EU Reg. 267/2012",
        force: false,
      });
    });
    expect(api.addBlockedCountry).toHaveBeenCalledWith({
      country_code: "IR",
      reason: "comprehensive_sanctions",
      basis: "EU Reg. 267/2012",
      force: false,
    });
    expect(invalidateSpy).toHaveBeenCalledWith({ queryKey: ["admin"] });
  });

  it("useDryRunBlockedCountry never invalidates and forwards dry_run", async () => {
    const { wrapper, invalidateSpy } = createWrapper();
    const { result } = renderHook(() => useDryRunBlockedCountry(), { wrapper });
    let counts: { affected_users: number; affected_marketplaces: number } | undefined;
    await act(async () => {
      counts = await result.current.mutateAsync({
        country_code: "IR",
        reason: "comprehensive_sanctions",
        basis: "EU Reg. 267/2012",
      });
    });
    expect(counts).toEqual({ affected_users: 3, affected_marketplaces: 0 });
    expect(api.dryRunBlockedCountry).toHaveBeenCalledTimes(1);
    expect(invalidateSpy).not.toHaveBeenCalled();
  });

  it("useRemoveBlockedCountry and useCompleteReview invalidate admin queries", async () => {
    const { wrapper, invalidateSpy } = createWrapper();
    const remove = renderHook(() => useRemoveBlockedCountry(), { wrapper });
    const review = renderHook(() => useCompleteReview(), { wrapper });
    await act(async () => {
      await remove.result.current.mutateAsync("RU");
      await review.result.current.mutateAsync("checked against sanctionsmap.eu");
    });
    expect(api.removeBlockedCountry).toHaveBeenCalledWith("RU");
    expect(api.completeBlockedCountriesReview).toHaveBeenCalledWith("checked against sanctionsmap.eu");
    expect(invalidateSpy).toHaveBeenCalledTimes(2);
  });

  it("useBlockedCountriesAudit passes the cursor and respects enabled", async () => {
    const { wrapper } = createWrapper();
    const disabled = renderHook(() => useBlockedCountriesAudit(null, false), { wrapper });
    expect(disabled.result.current.fetchStatus).toBe("idle");
    expect(api.getBlockedCountriesAudit).not.toHaveBeenCalled();

    const paged = renderHook(() => useBlockedCountriesAudit("cursor-2", true), { wrapper });
    await waitFor(() => expect(paged.result.current.isSuccess).toBe(true));
    expect(api.getBlockedCountriesAudit).toHaveBeenCalledWith({ limit: 50, cursor: "cursor-2" });
  });
});
