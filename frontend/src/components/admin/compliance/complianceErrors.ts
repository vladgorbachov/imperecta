import axios from "axios";

export function errorStatus(error: unknown): number | undefined {
  return axios.isAxiosError(error) ? error.response?.status : undefined;
}

export function errorDetail(error: unknown): unknown {
  return axios.isAxiosError(error)
    ? (error.response?.data as { detail?: unknown } | undefined)?.detail
    : undefined;
}

export function isProtectedCountryError(error: unknown): boolean {
  return errorStatus(error) === 409 && errorDetail(error) === "protected_country";
}

/**
 * 422 from the add endpoint carries either a plain string or the list of
 * active marketplaces that block the change; flatten both to one line.
 */
export function describeDetail(detail: unknown, fallback: string): string {
  if (typeof detail === "string") {
    return detail;
  }
  if (Array.isArray(detail)) {
    const parts = detail
      .map((entry) => {
        if (typeof entry === "string") {
          return entry;
        }
        if (entry && typeof entry === "object") {
          const record = entry as { name?: unknown; domain?: unknown; msg?: unknown };
          return String(record.name ?? record.domain ?? record.msg ?? "");
        }
        return "";
      })
      .filter(Boolean);
    return parts.length > 0 ? parts.join(", ") : fallback;
  }
  return fallback;
}
