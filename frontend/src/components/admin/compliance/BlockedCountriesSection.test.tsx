// @vitest-environment happy-dom

import "@testing-library/jest-dom/vitest";
import { AxiosError, type AxiosResponse, type InternalAxiosRequestConfig } from "axios";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { MemoryRouter } from "react-router-dom";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { TooltipProvider } from "@/components/ui/tooltip";
import { BlockedCountriesSection } from "@/components/admin/compliance/BlockedCountriesSection";

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

vi.mock("@/api/admin", async (importOriginal) => ({
  ...(await importOriginal<typeof import("@/api/admin")>()),
  ...api,
}));

vi.mock("sonner", () => ({
  toast: { success: vi.fn(), error: vi.fn() },
}));


const blockedRow = {
  country_code: "IR",
  name: "Iran",
  reason: "comprehensive_sanctions" as const,
  basis: "EU Reg. 267/2012; OFAC Iran programme",
  note: null,
  is_active: true,
  added_by: null,
  added_at: "2026-09-19T00:00:00Z",
  updated_at: "2026-09-19T00:00:00Z",
  review_due_at: "2026-12-18",
  is_protected: false,
  affected_users: 2,
  affected_marketplaces: 0,
};

const availableRows = [
  { code: "AF", name: "Afghanistan", in_dim_country: false, is_blocked: false, is_protected: false },
  { code: "DE", name: "Germany", in_dim_country: true, is_blocked: false, is_protected: true },
  { code: "IR", name: "Iran", in_dim_country: false, is_blocked: true, is_protected: false },
];

function axiosFailure(status: number, detail: unknown): AxiosError {
  const config = {} as InternalAxiosRequestConfig;
  const response = { status, data: { detail }, statusText: "", headers: {}, config } as AxiosResponse;
  return new AxiosError("request failed", String(status), config, undefined, response);
}

function renderSection() {
  const queryClient = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  });
  return render(
    <QueryClientProvider client={queryClient}>
      <TooltipProvider>
        <MemoryRouter>
          <BlockedCountriesSection />
        </MemoryRouter>
      </TooltipProvider>
    </QueryClientProvider>,
  );
}

async function openAddDialogWithBasis(country = "AF") {
  fireEvent.click(screen.getByRole("button", { name: /admin.compliance.add.button/ }));
  const dialog = await screen.findByTestId("blocked-country-dialog");
  fireEvent.change(within(dialog).getByTestId("country-picker-search"), {
    target: { value: country },
  });
  fireEvent.click(await within(dialog).findByRole("button", { name: new RegExp(country) }));
  fireEvent.change(within(dialog).getByLabelText("admin.compliance.add.basis"), {
    target: { value: "EU Reg. 2011/753" },
  });
  return dialog;
}

describe("Compliance — blocked countries section", () => {
  afterEach(() => cleanup());

  beforeEach(() => {
    vi.clearAllMocks();
    api.getBlockedCountries.mockResolvedValue({
      data: { items: [blockedRow], last_reviewed_at: "2026-09-01", next_review_due_at: "2026-12-18" },
    });
    api.getAvailableCountries.mockResolvedValue({ data: availableRows });
    api.dryRunBlockedCountry.mockResolvedValue({
      data: { affected_users: 5, affected_marketplaces: 0 },
    });
    api.addBlockedCountry.mockResolvedValue({ data: { ...blockedRow, country_code: "AF", name: "Afghanistan" } });
    api.completeBlockedCountriesReview.mockResolvedValue({
      data: { last_reviewed_at: "2026-09-19", next_review_due_at: "2026-12-18" },
    });
  });

  it("renders the table with reason badge, seed marker and review banner", async () => {
    renderSection();
    const row = await screen.findByTestId("blocked-row-IR");
    expect(within(row).getByText("Iran")).toBeInTheDocument();
    expect(within(row).getByText("admin.compliance.reason.comprehensive_sanctions")).toBeInTheDocument();
    expect(within(row).getByText("admin.compliance.table.seeded")).toBeInTheDocument();
    const banner = screen.getByTestId("review-banner");
    expect(within(banner).queryByText("admin.compliance.review.overdue")).not.toBeInTheDocument();
    expect(within(banner).getByRole("button", { name: "admin.compliance.review.markComplete" })).toBeInTheDocument();
  });

  it("flags an overdue review in the banner", async () => {
    api.getBlockedCountries.mockResolvedValue({
      data: { items: [blockedRow], last_reviewed_at: null, next_review_due_at: "2020-01-01" },
    });
    renderSection();
    const banner = await screen.findByTestId("review-banner");
    expect(within(banner).getByText(/admin.compliance.review.overdue/)).toBeInTheDocument();
    expect(within(banner).getByText("admin.compliance.review.never")).toBeInTheDocument();
  });

  it("marks the review complete after confirmation", async () => {
    renderSection();
    fireEvent.click(await screen.findByRole("button", { name: "admin.compliance.review.markComplete" }));
    const confirm = await screen.findByText("admin.compliance.review.confirmTitle");
    expect(confirm).toBeInTheDocument();
    const buttons = screen.getAllByRole("button", { name: "admin.compliance.review.markComplete" });
    fireEvent.click(buttons[buttons.length - 1]);
    await waitFor(() => expect(api.completeBlockedCountriesReview).toHaveBeenCalledTimes(1));
  });

  it("shows dry-run counts and enables save only when no marketplaces are affected", async () => {
    renderSection();
    await screen.findByTestId("blocked-row-IR");
    const dialog = await openAddDialogWithBasis("AF");
    const submit = within(dialog).getByTestId("blocked-country-submit");
    expect(submit).toBeDisabled();

    fireEvent.click(within(dialog).getByRole("button", { name: "admin.compliance.add.preview" }));
    await within(dialog).findByTestId("impact-preview");
    expect(api.dryRunBlockedCountry).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "AF", basis: "EU Reg. 2011/753", force: false }),
    );
    expect(within(dialog).getByText("admin.compliance.add.impact")).toBeInTheDocument();
    expect(submit).toBeEnabled();

    fireEvent.click(submit);
    await waitFor(() => expect(api.addBlockedCountry).toHaveBeenCalledTimes(1));
    expect(api.addBlockedCountry).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "AF", force: false }),
    );
  });

  it("blocks saving while active marketplaces exist in the country", async () => {
    api.dryRunBlockedCountry.mockResolvedValue({
      data: { affected_users: 1, affected_marketplaces: 3 },
    });
    renderSection();
    await screen.findByTestId("blocked-row-IR");
    const dialog = await openAddDialogWithBasis("AF");
    fireEvent.click(within(dialog).getByRole("button", { name: "admin.compliance.add.preview" }));
    await within(dialog).findByTestId("impact-preview");
    expect(within(dialog).getByText(/admin.compliance.add.marketplacesBlock/)).toBeInTheDocument();
    expect(within(dialog).getByRole("link", { name: "admin.compliance.add.marketplacesLink" })).toHaveAttribute(
      "href",
      "/admin/overview",
    );
    expect(within(dialog).getByTestId("blocked-country-submit")).toBeDisabled();
  });

  it("disables already blocked countries in the picker", async () => {
    renderSection();
    await screen.findByTestId("blocked-row-IR");
    fireEvent.click(screen.getByRole("button", { name: /admin.compliance.add.button/ }));
    const dialog = await screen.findByTestId("blocked-country-dialog");
    const iranOption = await within(dialog).findByRole("button", { name: /Iran/ });
    expect(iranOption).toBeDisabled();
    expect(within(iranOption).getByText("admin.compliance.add.alreadyBlocked")).toBeInTheDocument();
  });

  it("routes a 409 protected_country through the legal warning and retries with force", async () => {
    api.dryRunBlockedCountry
      .mockRejectedValueOnce(axiosFailure(409, "protected_country"))
      .mockResolvedValueOnce({ data: { affected_users: 0, affected_marketplaces: 0 } });
    renderSection();
    await screen.findByTestId("blocked-row-IR");
    const dialog = await openAddDialogWithBasis("DE");
    fireEvent.click(within(dialog).getByRole("button", { name: "admin.compliance.add.preview" }));

    const warning = await screen.findByTestId("protected-country-warning");
    expect(within(warning).getByText("admin.compliance.protectedWarning")).toBeInTheDocument();
    const confirm = within(warning).getByRole("button", { name: "admin.compliance.protected.confirm" });
    expect(confirm).toBeDisabled();
    fireEvent.change(within(warning).getByLabelText("admin.compliance.protected.noteLabel"), {
      target: { value: "Council Decision (CFSP) 2026/1 — specific listing" },
    });
    expect(confirm).toBeEnabled();
    fireEvent.click(confirm);

    await waitFor(() => expect(api.dryRunBlockedCountry).toHaveBeenCalledTimes(2));
    expect(api.dryRunBlockedCountry).toHaveBeenLastCalledWith(
      expect.objectContaining({
        country_code: "DE",
        force: true,
        note: expect.stringContaining("Council Decision"),
      }),
    );
    await within(dialog).findByTestId("impact-preview");

    fireEvent.click(within(dialog).getByTestId("blocked-country-submit"));
    await waitFor(() => expect(api.addBlockedCountry).toHaveBeenCalledTimes(1));
    expect(api.addBlockedCountry).toHaveBeenCalledWith(
      expect.objectContaining({ country_code: "DE", force: true }),
    );
  });

  it("confirms removal with the country name", async () => {
    api.removeBlockedCountry.mockResolvedValue({});
    renderSection();
    const row = await screen.findByTestId("blocked-row-IR");
    fireEvent.click(within(row).getByRole("button", { name: "common.delete" }));
    await screen.findByText("admin.compliance.remove.title");
    fireEvent.click(screen.getByRole("button", { name: "admin.compliance.remove.confirm" }));
    await waitFor(() => expect(api.removeBlockedCountry).toHaveBeenCalledWith("IR"));
  });

  it("runs the IP check from the footer form", async () => {
    api.checkIpCountry.mockResolvedValue({
      data: { ip: "1.2.3.4", country: "IR", blocked: true, provider: "cloudflare" },
    });
    renderSection();
    await screen.findByTestId("blocked-row-IR");
    fireEvent.change(screen.getByLabelText("admin.compliance.ipCheck.title"), {
      target: { value: "1.2.3.4" },
    });
    fireEvent.click(screen.getByRole("button", { name: "admin.compliance.ipCheck.button" }));
    const result = await screen.findByTestId("ip-check-result");
    expect(result).toHaveTextContent("1.2.3.4");
    expect(result).toHaveTextContent("admin.compliance.ipCheck.blocked");
    expect(api.checkIpCountry).toHaveBeenCalledWith("1.2.3.4");
  });
});
