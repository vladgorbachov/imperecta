// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterPage } from "./RegisterPage";

const registerMock = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (state: { register: typeof registerMock; accessToken: null }) => unknown) =>
    selector({ register: registerMock, accessToken: null }),
}));

vi.mock("@/hooks/useLegalDocuments", () => ({
  useLegalDocuments: () => ({
    terms: { document: "terms", version: "v-terms", path: "/legal/terms" },
    privacy: { document: "privacy", version: "v-privacy", path: "/legal/privacy" },
    aup: { document: "aup", version: "v-aup", path: "/legal/aup" },
  }),
}));

vi.mock("@/hooks/useSignupCountries", () => ({
  useSignupCountries: () => ({
    countries: [
      { code: "MD", name: "Moldova" },
      { code: "LV", name: "Latvia" },
    ],
    isLoading: false,
  }),
}));

function renderPage() {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={["/register"]}>
        <RegisterPage />
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

function acceptConsents() {
  fireEvent.click(screen.getByRole("radio", { name: "auth.accountType.business" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "auth.businessUseConfirm" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "auth.adultConfirm" }));
  fireEvent.click(screen.getByRole("checkbox", { name: "auth.acceptDocuments.aria" }));
}

function fillIdentity() {
  fireEvent.change(screen.getByLabelText("auth.name"), { target: { value: "Ada" } });
  fireEvent.change(screen.getByLabelText("auth.email"), { target: { value: "ada@example.com" } });
  fireEvent.change(screen.getByLabelText("auth.password"), { target: { value: "Str0ng!Passw0rd" } });
  fireEvent.change(screen.getByLabelText("auth.confirmPassword"), {
    target: { value: "Str0ng!Passw0rd" },
  });
}

describe("RegisterPage — country", () => {
  afterEach(() => cleanup());
  beforeEach(() => {
    vi.clearAllMocks();
    registerMock.mockResolvedValue(undefined);
  });

  it("lists the signup countries and requires one before submitting", async () => {
    renderPage();
    const select = screen.getByTestId("register-country") as HTMLSelectElement;
    expect(select.options.length).toBe(3);
    expect(select.options[1].value).toBe("MD");

    fillIdentity();
    acceptConsents();
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(screen.getByText("auth.fieldRequired")).toBeInTheDocument());
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("requires the account type and every consent", async () => {
    renderPage();
    fillIdentity();
    fireEvent.change(screen.getByTestId("register-country"), { target: { value: "MD" } });
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(screen.getByText("auth.accountType.required")).toBeInTheDocument());
    fireEvent.click(screen.getByRole("radio", { name: "auth.accountType.soleTrader" }));
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(screen.getByText("auth.consentRequired")).toBeInTheDocument());
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("sends country, account type, confirmations and document versions", async () => {
    renderPage();
    fillIdentity();
    fireEvent.change(screen.getByTestId("register-country"), { target: { value: "LV" } });
    acceptConsents();
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(registerMock).toHaveBeenCalledTimes(1));
    expect(registerMock).toHaveBeenCalledWith(
      expect.objectContaining({
        countryCode: "LV",
        accountType: "business",
        businessUseConfirmed: true,
        adultConfirmed: true,
        termsVersion: "v-terms",
        privacyVersion: "v-privacy",
      }),
    );
  });

  it("maps 422 country_not_supported to the country error", async () => {
    registerMock.mockRejectedValue({
      response: { status: 422, data: { detail: "country_not_supported" } },
    });
    renderPage();
    fillIdentity();
    fireEvent.change(screen.getByTestId("register-country"), { target: { value: "MD" } });
    acceptConsents();
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() =>
      expect(screen.getAllByText("auth.countryNotSupported").length).toBeGreaterThanOrEqual(1),
    );
  });
});
