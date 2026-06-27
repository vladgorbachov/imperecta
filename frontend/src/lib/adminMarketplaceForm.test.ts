import { describe, expect, it } from "vitest";
import {
  buildEditMarketplaceForm,
  canSubmitAddMarketplace,
  formatAdminCountryLabel,
} from "./adminMarketplaceForm";

describe("adminMarketplaceForm", () => {
  it("prefills edit form from marketplace country_code", () => {
    expect(
      buildEditMarketplaceForm({
        name: "Shop",
        base_url: "https://shop.example",
        country_code: "LT",
      }),
    ).toEqual({
      name: "Shop",
      url: "https://shop.example",
      country_code: "LT",
    });
  });

  it("blocks add submit without country", () => {
    expect(canSubmitAddMarketplace("https://shop.example", "", false)).toBe(false);
    expect(canSubmitAddMarketplace("https://shop.example", "LT", false)).toBe(true);
    expect(canSubmitAddMarketplace("", "LT", false)).toBe(false);
    expect(canSubmitAddMarketplace("https://shop.example", "LT", true)).toBe(false);
  });

  it("uses i18n country label with API fallback", () => {
    const t = (key: string) => (key === "countries.ZZ" ? "World" : key);
    expect(formatAdminCountryLabel("ZZ", "World", t)).toBe("World");
    expect(formatAdminCountryLabel("XX", "Fallback Name", t)).toBe("Fallback Name");
  });
});
