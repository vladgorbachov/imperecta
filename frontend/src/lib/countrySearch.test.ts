/**
 * Multilingual country search tests.
 * Verifies search normalization and matching for all supported scripts.
 */

import { describe, it, expect } from "vitest";
import {
  normalizeForSearch,
  matchesCountrySearch as matchesSearch,
} from "./countrySearch";

describe("normalizeForSearch", () => {
  it("lowercases Latin script", () => {
    expect(normalizeForSearch("Russia", "en")).toBe("russia");
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
    expect(matchesSearch("Russia", "RU", "russia", "en")).toBe(true);
    expect(matchesSearch("Russia", "RU", "Russ", "en")).toBe(true);
    expect(matchesSearch("United States", "US", "united", "en")).toBe(true);
  });

  it("matches Russian label with Russian search", () => {
    expect(matchesSearch("Россия", "RU", "россия", "ru")).toBe(true);
    expect(matchesSearch("Россия", "RU", "рос", "ru")).toBe(true);
  });

  it("matches Ukrainian label with Ukrainian search", () => {
    expect(matchesSearch("Україна", "UA", "україна", "uk")).toBe(true);
  });

  it("matches by country code", () => {
    expect(matchesSearch("Russia", "RU", "ru", "en")).toBe(true);
    expect(matchesSearch("Россия", "RU", "RU", "ru")).toBe(true);
  });

  it("does not match when search does not match", () => {
    expect(matchesSearch("Russia", "RU", "Germany", "en")).toBe(false);
    expect(matchesSearch("Россия", "RU", "Germany", "ru")).toBe(false);
  });

  it("handles Chinese search", () => {
    expect(matchesSearch("中国", "CN", "中国", "zh")).toBe(true);
    expect(matchesSearch("中国", "CN", "中", "zh")).toBe(true);
  });

  it("handles Arabic search", () => {
    expect(matchesSearch("روسيا", "RU", "روسيا", "ar")).toBe(true);
  });
});
