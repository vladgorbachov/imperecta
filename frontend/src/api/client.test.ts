// @vitest-environment happy-dom

import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { beforeAll, beforeEach, describe, expect, it, vi } from "vitest";

vi.stubEnv("VITE_API_URL", "https://api.test.local");

type ClientModule = typeof import("./client");
let client: ClientModule;

function axiosFailure(status: number, data: unknown): AxiosError {
  const config = {} as InternalAxiosRequestConfig;
  const response = { status, data, statusText: "", headers: {}, config } as AxiosResponse;
  return new AxiosError("request failed", String(status), config, undefined, response);
}

describe("api client — HTTP 451 handling", () => {
  beforeAll(async () => {
    client = await import("./client");
  });

  beforeEach(() => {
    localStorage.setItem("imperecta_auth", JSON.stringify({ accessToken: "t" }));
    sessionStorage.setItem("imperecta_auth_session", JSON.stringify({ accessToken: "t" }));
  });

  it("recognises only the fixed compliance body", () => {
    expect(
      client.isBlockedCountryResponse(
        axiosFailure(451, { detail: "service_unavailable_in_your_country", country: "IR" }),
      ),
    ).toBe(true);
    expect(client.isBlockedCountryResponse(axiosFailure(451, { detail: "other" }))).toBe(false);
    expect(
      client.isBlockedCountryResponse(axiosFailure(403, { detail: "service_unavailable_in_your_country" })),
    ).toBe(false);
    expect(client.isBlockedCountryResponse(new Error("network"))).toBe(false);
  });

  it("clears the stored session and redirects to /blocked on 451", async () => {
    const navigate = vi.fn();
    const error = axiosFailure(451, { detail: "service_unavailable_in_your_country", country: "IR" });
    await expect(client.handleBlockedCountryError(error, navigate)).rejects.toBe(error);
    expect(navigate).toHaveBeenCalledWith("/blocked");
    expect(localStorage.getItem("imperecta_auth")).toBeNull();
    expect(sessionStorage.getItem("imperecta_auth_session")).toBeNull();
  });

  it("passes every other error through untouched", async () => {
    const navigate = vi.fn();
    const error = axiosFailure(401, { detail: "unauthorized" });
    await expect(client.handleBlockedCountryError(error, navigate)).rejects.toBe(error);
    expect(navigate).not.toHaveBeenCalled();
    expect(localStorage.getItem("imperecta_auth")).not.toBeNull();
  });
});
