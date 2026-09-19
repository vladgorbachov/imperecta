import { describe, expect, it } from "vitest";
import {
  assertTranslationKey,
  findMissingLanguagesForKey,
  flattenTranslationKeys,
  validateTranslationCoverage,
  type TranslationResourceMap,
} from "../translationGuard";

describe("translationGuard", () => {
  it("flattens nested translation dictionaries", () => {
    const keys = flattenTranslationKeys({
      dashboard: {
        title: "Dashboard",
        stats: {
          products: "Products",
        },
      },
      "common.save": "Save",
    });

    expect([...keys].sort()).toEqual([
      "common.save",
      "dashboard.stats.products",
      "dashboard.title",
    ]);
  });

  it("reports missing keys for each target language", () => {
    const resources: TranslationResourceMap = {
      en: { "dashboard.title": "Dashboard", "common.save": "Save" },
      fr: { "dashboard.title": "Tableau de bord" },
      uk: { "common.save": "Зберегти" },
    };

    const result = validateTranslationCoverage(resources, "en", ["fr", "uk"]);
    expect(result.totalBaseKeys).toBe(2);
    expect(result.missingByLanguage.fr).toEqual(["common.save"]);
    expect(result.missingByLanguage.uk).toEqual(["dashboard.title"]);
    expect(result.hasMissingKeys).toBe(true);
  });

  it("finds missing languages for one key", () => {
    const resources: TranslationResourceMap = {
      en: { "nav.dashboard": "Dashboard" },
      fr: { "nav.dashboard": "Tableau de bord" },
      ro: {},
    };
    const missing = findMissingLanguagesForKey(resources, "nav.dashboard", ["en", "fr", "ro"]);
    expect(missing).toEqual(["ro"]);
  });

  it("does not throw in development when key exists everywhere", () => {
    const resources: TranslationResourceMap = {
      en: { "settings.language": "Language" },
      fr: { "settings.language": "Langue" },
      ro: { "settings.language": "Limbă" },
    };
    expect(() => assertTranslationKey("settings.language", resources, ["en", "fr", "ro"])).not.toThrow();
  });
});

