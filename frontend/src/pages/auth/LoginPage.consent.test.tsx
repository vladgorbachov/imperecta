// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { LoginPage } from "./LoginPage";

const loginMock = vi.fn();
const authState = { login: loginMock, accessToken: null as string | null };

vi.mock("@/stores/authStore", () => ({
  useAuthStore: Object.assign(
    (selector: (state: typeof authState) => unknown) => selector(authState),
    { getState: () => authState },
  ),
}));

vi.mock("@/api/auth", () => ({
  authApi: {
    getLegalDocuments: () => Promise.reject(new Error("not deployed")),
  },
}));

function axiosFailure(status: number, data: unknown): AxiosError {
  const config = {} as InternalAxiosRequestConfig;
  const response = { status, data, statusText: "", headers: {}, config } as AxiosResponse;
  return new AxiosError("request failed", String(status), config, undefined, response);
}

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/login"]}>
        <LoginPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function submitCredentials() {
  fireEvent.change(screen.getByLabelText("auth.email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("auth.password"), { target: { value: "Str0ng!Passw0rd" } });
  fireEvent.submit(screen.getByRole("button", { name: "auth.submitLogin" }).closest("form")!);
}

describe("LoginPage — re-consent", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
    authState.accessToken = null;
  });

  it("shows the consent step on 409 consent_required and resubmits with consents", async () => {
    loginMock
      .mockRejectedValueOnce(
        axiosFailure(409, {
          detail: "consent_required",
          required_consents: [{ document: "terms", version: "2027-01-01", url: null }],
        }),
      )
      .mockResolvedValueOnce({ success: true, forcePasswordChange: false });

    renderPage();
    submitCredentials();
    const step = await screen.findByTestId("consent-step");
    expect(step).toBeInTheDocument();

    const confirm = screen.getByRole("button", { name: "auth.consentConfirm" });
    expect(confirm).toBeDisabled();
    fireEvent.click(screen.getByRole("checkbox", { name: "auth.acceptDocuments.aria" }));
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(loginMock).toHaveBeenCalledTimes(2));
    expect(loginMock.mock.calls[1][0]).toEqual(
      expect.objectContaining({
        email: "ada@example.com",
        consents: [{ document: "terms", version: expect.any(String) }],
      }),
    );
  });

  it("keeps ordinary login errors on the form", async () => {
    loginMock.mockRejectedValueOnce(axiosFailure(401, { detail: "Invalid credentials" }));
    renderPage();
    submitCredentials();
    await waitFor(() => expect(screen.getByText("Invalid credentials")).toBeInTheDocument());
    expect(screen.queryByTestId("consent-step")).not.toBeInTheDocument();
  });
});
