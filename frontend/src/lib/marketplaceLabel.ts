import { getCountryByCode } from "@/lib/countries";

/** Global storefronts where the marketplace name alone is sufficient. */
const KNOWN_INTERNATIONAL_DOMAINS = new Set([
  "amazon.com",
  "ebay.com",
  "aliexpress.com",
  "etsy.com",
  "walmart.com",
]);

export interface MarketplaceLabelInput {
  name?: string | null;
  domain?: string | null;
  countryCode?: string | null;
  locale?: string;
}

/** Normalize domain for comparisons (lowercase, strip www). */
export function normalizeMarketplaceDomain(domain: string): string {
  return domain.toLowerCase().replace(/^www\./, "").trim();
}

/** Whether the domain uses a country-code TLD (e.g. barbora.lv, kaufland.de). */
export function isCountryTldDomain(domain: string): boolean {
  const normalized = normalizeMarketplaceDomain(domain);
  const parts = normalized.split(".").filter(Boolean);
  if (parts.length < 2) {
    return false;
  }
  const tld = parts[parts.length - 1];
  if (tld.length === 2 && getCountryByCode(tld.toUpperCase())) {
    return true;
  }
  const secondLevel = parts[parts.length - 2];
  if (secondLevel.length === 2 && getCountryByCode(secondLevel.toUpperCase())) {
    return true;
  }
  return false;
}

/**
 * International marketplaces (ebay.com, amazon.com) are shown without a country suffix.
 * Local country-specific domains are not international.
 */
export function isInternationalMarketplace(domain?: string | null): boolean {
  if (!domain) {
    return false;
  }
  const normalized = normalizeMarketplaceDomain(domain);
  if (KNOWN_INTERNATIONAL_DOMAINS.has(normalized)) {
    return true;
  }
  if (isCountryTldDomain(normalized)) {
    return false;
  }
  const parts = normalized.split(".").filter(Boolean);
  return parts.length === 2 && parts[1] === "com";
}

/** Localized country label for marketplace suffixes. */
export function getCountryDisplayName(code: string, locale?: string): string {
  const info = getCountryByCode(code);
  if (!info) {
    return code.toUpperCase();
  }
  const lang = (locale ?? "en").split("-")[0].toLowerCase();
  if (lang === "ru" && info.name_local) {
    return info.name_local;
  }
  return info.name;
}

/**
 * Build a user-facing marketplace label.
 * Local pool marketplaces with a country code get a country suffix; global .com stores do not.
 */
export function formatMarketplaceLabel({
  name,
  domain,
  countryCode,
  locale,
}: MarketplaceLabelInput): string {
  const base = (name?.trim() || domain?.trim() || "").replace(/_/g, " ");
  if (!base) {
    return "";
  }
  if (isInternationalMarketplace(domain)) {
    return base;
  }
  if (countryCode) {
    const country = getCountryDisplayName(countryCode, locale);
    return `${base} (${country})`;
  }
  return base;
}
