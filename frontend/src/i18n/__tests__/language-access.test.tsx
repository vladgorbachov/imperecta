import { describe, expect, it } from "vitest";
import {
  PUBLIC_LANGUAGE_CODES,
  SUPPORTED_LANGUAGE_CODES,
  enforceLanguagePolicy,
  getAvailableLanguages,
} from "../index";

describe("language access policy", () => {
  it("keeps Russian in supported language list", () => {
    expect(SUPPORTED_LANGUAGE_CODES).toContain("ru");
  });

  it("excludes Russian from public languages", () => {
    expect(PUBLIC_LANGUAGE_CODES).not.toContain("ru");
  });

  it("returns Russian only for admin users", () => {
    const publicCodes = getAvailableLanguages(false).map((language) => language.code);
    const adminCodes = getAvailableLanguages(true).map((language) => language.code);

    expect(publicCodes).not.toContain("ru");
    expect(adminCodes).toContain("ru");
  });

  it("hides Russian from non-admin available options", () => {
    const publicNames = getAvailableLanguages(false).map((language) => language.name);
    const adminNames = getAvailableLanguages(true).map((language) => language.name);

    expect(publicNames).not.toContain("Русский");
    expect(adminNames).toContain("Русский");
  });

  it("forces non-admin language from ru to en", () => {
    localStorage.setItem("imperecta_language", "ru");
    enforceLanguagePolicy(false);

    expect(localStorage.getItem("imperecta_language")).toBe("en");
  });
});

