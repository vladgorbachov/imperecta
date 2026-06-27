// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { renderHook, waitFor } from "@testing-library/react";
import { type ReactNode } from "react";
import { beforeEach, describe, expect, it, vi } from "vitest";
import { useAddMarketplace, useCountries } from "./useAdmin";
import * as adminApi from "@/api/admin";

vi.mock("@/api/markets", () => ({
  marketsApi: {
    triggerIngest: vi.fn(),
  },
  marketsQueryKeys: {
    all: ["markets"],
  },
}));

vi.mock("@/api/admin", () => ({
  getCountries: vi.fn(),
  addMarketplace: vi.fn(),
}));

function createWrapper(client: QueryClient) {
  return ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  );
}

describe("useAdmin marketplace hooks", () => {
  beforeEach(() => {
    vi.clearAllMocks();
  });

  it("loads countries from admin reference endpoint", async () => {
    vi.mocked(adminApi.getCountries).mockResolvedValue({
      data: [
        {
          code: "LT",
          name: "Lithuania",
          name_local: null,
          region: "europe",
          currency_code: "EUR",
        },
        {
          code: "ZZ",
          name: "World",
          name_local: null,
          region: "world",
          currency_code: "EUR",
        },
      ],
    } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useCountries(), {
      wrapper: createWrapper(queryClient),
    });

    await waitFor(() => {
      expect(result.current.data).toHaveLength(2);
    });
    expect(result.current.data?.[1]?.code).toBe("ZZ");
    expect(adminApi.getCountries).toHaveBeenCalledTimes(1);
  });

  it("creates marketplace with explicit country_code", async () => {
    vi.mocked(adminApi.addMarketplace).mockResolvedValue({ data: {} } as never);

    const queryClient = new QueryClient({
      defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
    });
    const { result } = renderHook(() => useAddMarketplace(), {
      wrapper: createWrapper(queryClient),
    });

    await result.current.mutateAsync({
      url: "https://shop.example.com",
      country_code: "LT",
    });

    expect(adminApi.addMarketplace).toHaveBeenCalledWith({
      url: "https://shop.example.com",
      country_code: "LT",
    });
  });
});
