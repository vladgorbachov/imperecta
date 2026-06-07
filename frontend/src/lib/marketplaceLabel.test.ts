import { describe, expect, it } from "vitest";
import {
  formatMarketplaceLabel,
  isInternationalMarketplace,
} from "./marketplaceLabel";

describe("isInternationalMarketplace", () => {
  it("treats ebay.com and amazon.com as international", () => {
    expect(isInternationalMarketplace("ebay.com")).toBe(true);
    expect(isInternationalMarketplace("www.amazon.com")).toBe(true);
  });

  it("treats country TLD domains as local", () => {
    expect(isInternationalMarketplace("barbora.lv")).toBe(false);
    expect(isInternationalMarketplace("kaufland.de")).toBe(false);
  });
});

describe("formatMarketplaceLabel", () => {
  it("appends country for duplicate local marketplaces", () => {
    expect(
      formatMarketplaceLabel({
        name: "Barbora",
        domain: "barbora.lv",
        countryCode: "LV",
        locale: "en",
      }),
    ).toBe("Barbora (Latvia)");

    expect(
      formatMarketplaceLabel({
        name: "Barbora",
        domain: "barbora.lt",
        countryCode: "LT",
        locale: "ru",
      }),
    ).toBe("Barbora (Литва)");
  });

  it("keeps international marketplace name without country", () => {
    expect(
      formatMarketplaceLabel({
        name: "eBay",
        domain: "ebay.com",
        countryCode: "US",
        locale: "en",
      }),
    ).toBe("eBay");
  });

  it("falls back to domain when name is missing", () => {
    expect(
      formatMarketplaceLabel({
        domain: "barbora.lv",
        countryCode: "LV",
        locale: "en",
      }),
    ).toBe("barbora.lv (Latvia)");
  });
});
