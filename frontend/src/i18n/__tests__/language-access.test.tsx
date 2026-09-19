import { describe, expect, it } from "vitest";
import {
  SUPPORTED_LANGUAGES,
  SUPPORTED_LANGUAGE_CODES,
  getAvailableLanguages,
  isSupportedLanguage,
} from "../index";

describe("language access policy", () => {
  it("ships exactly the seven public UI languages", () => {
    expect([...SUPPORTED_LANGUAGE_CODES]).toEqual(["en", "ar", "es", "zh", "fr", "ro", "uk"]);
  });

  it("offers every supported language to every user", () => {
    expect(getAvailableLanguages().map((language) => language.code)).toEqual([
      ...SUPPORTED_LANGUAGE_CODES,
    ]);
    expect(SUPPORTED_LANGUAGES).toHaveLength(SUPPORTED_LANGUAGE_CODES.length);
  });

  it("rejects codes outside the supported list", () => {
    expect(isSupportedLanguage("en")).toBe(true);
    expect(isSupportedLanguage("uk")).toBe(true);
    expect(isSupportedLanguage("xx")).toBe(false);
    expect(isSupportedLanguage("en-GB")).toBe(false);
  });
});
