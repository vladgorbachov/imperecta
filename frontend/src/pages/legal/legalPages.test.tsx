// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { MemoryRouter, Route, Routes } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { BotPolicyPage } from "./BotPolicyPage";
import { LegalDocumentPage } from "./LegalDocumentPage";
import { TrustPage } from "./TrustPage";

const optOutMock = vi.fn();
vi.mock("@/api/bot", () => ({
  botApi: { optOut: (...args: unknown[]) => optOutMock(...args) },
}));
vi.mock("@/api/auth", () => ({
  authApi: { getLegalDocuments: () => Promise.reject(new Error("not deployed")) },
}));

function renderAt(path: string) {
  const queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return render(
    <QueryClientProvider client={queryClient}>
      <MemoryRouter initialEntries={[path]}>
        <Routes>
          <Route path="/legal" element={<LegalDocumentPage />} />
          <Route path="/legal/:document" element={<LegalDocumentPage />} />
          <Route path="/bot" element={<BotPolicyPage />} />
          <Route path="/trust" element={<TrustPage />} />
        </Routes>
      </MemoryRouter>
    </QueryClientProvider>,
  );
}

describe("public legal pages", () => {
  afterEach(() => cleanup());
  beforeEach(() => vi.clearAllMocks());

  it("renders a versioned document with the pending-text notice", () => {
    renderAt("/legal/privacy");
    expect(screen.getByRole("heading", { level: 1, name: "legal.privacy" })).toBeInTheDocument();
    expect(screen.getByText("legal.version")).toBeInTheDocument();
    expect(screen.getByTestId("legal-text-pending")).toBeInTheDocument();
  });

  it("links the data-sources document to the opt-out form and redirects unknown slugs", () => {
    renderAt("/legal/data-sources");
    expect(screen.getByRole("link", { name: "legal.optOutLink" })).toHaveAttribute("href", "/bot");
    expect(screen.queryByText("legal.version")).not.toBeInTheDocument();
    cleanup();
    renderAt("/legal/unknown");
    expect(screen.getByRole("heading", { level: 1, name: "legal.terms" })).toBeInTheDocument();
  });

  it("submits an opt-out request only with a valid domain and e-mail", async () => {
    optOutMock.mockResolvedValue({ data: { request_id: "req-42" } });
    renderAt("/bot");
    const submit = screen.getByRole("button", { name: "bot.optOut.submit" });
    expect(submit).toBeDisabled();
    fireEvent.change(screen.getByLabelText("bot.optOut.domain"), { target: { value: "Shop.Example" } });
    fireEvent.change(screen.getByLabelText("bot.optOut.email"), { target: { value: "ops@shop.example" } });
    expect(submit).toBeEnabled();
    fireEvent.click(submit);
    await waitFor(() => expect(optOutMock).toHaveBeenCalledTimes(1));
    expect(optOutMock).toHaveBeenCalledWith({
      domain: "shop.example",
      email: "ops@shop.example",
      message: undefined,
    });
    expect(await screen.findByText("bot.optOut.received")).toBeInTheDocument();
    expect(screen.getByText("req-42")).toBeInTheDocument();
  });

  it("renders the trust page sections", () => {
    renderAt("/trust");
    for (const key of ["attribution", "noExport", "crawler", "sanctions"]) {
      expect(screen.getByTestId(`trust-${key}`)).toBeInTheDocument();
    }
  });
});
