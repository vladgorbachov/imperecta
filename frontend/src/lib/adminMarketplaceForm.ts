import type { ParsingDetailedMarketplace } from "@/api/admin";

export interface EditMarketplaceFormState {
  name: string;
  url: string;
  country_code: string;
}

/** Seed edit dialog fields from a detailed marketplace row. */
export function buildEditMarketplaceForm(
  item: Pick<ParsingDetailedMarketplace, "name" | "base_url" | "country_code">,
): EditMarketplaceFormState {
  return {
    name: item.name,
    url: item.base_url,
    country_code: item.country_code,
  };
}

/** Whether add-marketplace submit is allowed (explicit country required). */
export function canSubmitAddMarketplace(
  url: string,
  countryCode: string,
  isPending: boolean,
): boolean {
  return !isPending && url.trim().length > 0 && countryCode.length > 0;
}

/** Localized country label with API name fallback. */
export function formatAdminCountryLabel(
  code: string,
  fallbackName: string,
  translate: (key: string) => string,
): string {
  const key = `countries.${code}`;
  const localized = translate(key);
  return localized !== key ? localized : fallbackName;
}
