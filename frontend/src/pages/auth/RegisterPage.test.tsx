// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { RegisterPage } from "./RegisterPage";

const registerMock = vi.fn();

vi.mock("@/stores/authStore", () => ({
  useAuthStore: (selector: (state: { register: typeof registerMock; accessToken: null }) => unknown) =>
    selector({ register: registerMock, accessToken: null }),
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
  return render(
    <MemoryRouter initialEntries={["/register"]}>
      <RegisterPage />
    </MemoryRouter>,
  );
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
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(screen.getByText("auth.fieldRequired")).toBeInTheDocument());
    expect(registerMock).not.toHaveBeenCalled();
  });

  it("sends the selected country code with the registration", async () => {
    renderPage();
    fillIdentity();
    fireEvent.change(screen.getByTestId("register-country"), { target: { value: "LV" } });
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() => expect(registerMock).toHaveBeenCalledTimes(1));
    expect(registerMock.mock.calls[0][5]).toBe("LV");
  });

  it("maps 422 country_not_supported to the country error", async () => {
    registerMock.mockRejectedValue({
      response: { status: 422, data: { detail: "country_not_supported" } },
    });
    renderPage();
    fillIdentity();
    fireEvent.change(screen.getByTestId("register-country"), { target: { value: "MD" } });
    fireEvent.submit(screen.getByRole("button", { name: "auth.submitRegister" }).closest("form")!);
    await waitFor(() =>
      expect(screen.getAllByText("auth.countryNotSupported").length).toBeGreaterThanOrEqual(1),
    );
  });
});
