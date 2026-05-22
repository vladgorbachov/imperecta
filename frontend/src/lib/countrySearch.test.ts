/**
 * Multilingual country search tests.
 * Verifies search normalization and matching for all supported scripts.
 */

import { describe, it, expect } from "vitest";
import {
  normalizeForSearch,
  matchesCountrySearch as matchesSearch,
} from "./countrySearch";
import { COUNTRIES } from "./countries";
import { resolveActiveCountry } from "./countryResolution";

describe("normalizeForSearch", () => {
  it("lowercases Latin script", () => {
    expect(normalizeForSearch("Ukraine", "en")).toBe("ukraine");
    expect(normalizeForSearch("UNITED STATES", "en")).toBe("united states");
  });

  it("lowercases Cyrillic script", () => {
    expect(normalizeForSearch("Россия", "ru")).toBe("россия");
    expect(normalizeForSearch("УКРАЇНА", "uk")).toBe("україна");
  });

  it("handles Arabic (no case, returns normalized)", () => {
    const result = normalizeForSearch("روسيا", "ar");
    expect(result).toBeTruthy();
    expect(result.length).toBeGreaterThan(0);
  });

  it("handles Chinese (no case, returns as-is or normalized)", () => {
    const result = normalizeForSearch("俄罗斯", "zh");
    expect(result).toBeTruthy();
    expect(result).toContain("俄");
  });

  it("trims whitespace", () => {
    expect(normalizeForSearch("  Russia  ", "en")).toBe("russia");
  });

  it("returns empty for empty input", () => {
    expect(normalizeForSearch("", "en")).toBe("");
    expect(normalizeForSearch("   ", "en")).toBe("");
  });
});

describe("matchesSearch", () => {
  it("matches English label with English search", () => {
    expect(matchesSearch("Ukraine", "UA", "ukraine", "en")).toBe(true);
    expect(matchesSearch("Ukraine", "UA", "ukr", "en")).toBe(true);
    expect(matchesSearch("United States", "US", "united", "en")).toBe(true);
  });

  it("matches Russian label with Russian search", () => {
    expect(matchesSearch("Украина", "UA", "украина", "ru")).toBe(true);
    expect(matchesSearch("Украина", "UA", "укра", "ru")).toBe(true);
  });

  it("matches Ukrainian label with Ukrainian search", () => {
    expect(matchesSearch("Україна", "UA", "україна", "uk")).toBe(true);
  });

  it("matches by country code", () => {
    expect(matchesSearch("Ukraine", "UA", "ua", "en")).toBe(true);
    expect(matchesSearch("Украина", "UA", "UA", "ru")).toBe(true);
  });

  it("does not match when search does not match", () => {
    expect(matchesSearch("Ukraine", "UA", "Germany", "en")).toBe(false);
    expect(matchesSearch("Украина", "UA", "Germany", "ru")).toBe(false);
  });

  it("handles Chinese search", () => {
    expect(matchesSearch("中国", "CN", "中国", "zh")).toBe(true);
    expect(matchesSearch("中国", "CN", "中", "zh")).toBe(true);
  });

  it("handles Arabic search", () => {
    expect(matchesSearch("أوكرانيا", "UA", "أوكرانيا", "ar")).toBe(true);
  });
});

describe("public country policy", () => {
  it("does not include RU or BY in public country list", () => {
    const codes = COUNTRIES.map((country) => country.code);
    expect(codes).not.toContain("RU");
    expect(codes).not.toContain("BY");
  });

  it("never returns RU/BY from public country resolution", () => {
    expect(resolveActiveCountry("RU", null, "en")).not.toBe("RU");
    expect(resolveActiveCountry("BY", null, "en")).not.toBe("BY");
    expect(resolveActiveCountry(null, "RU", "en")).not.toBe("RU");
    expect(resolveActiveCountry(null, "BY", "en")).not.toBe("BY");
  });

  it("locale ru resolves to UA fallback", () => {
    expect(resolveActiveCountry(null, null, "ru")).toBe("UA");
    expect(resolveActiveCountry(null, null, "ru-RU")).toBe("UA");
  });
});
