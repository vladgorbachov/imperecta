/**
 * Locale-aware formatters for prices, dates, and relative time.
 * Use i18n.language as locale parameter for consistency with app language.
 */

/**
 * Formats a price amount using Intl.NumberFormat.
 * @example formatPrice(12450, "RUB", "ru") → "12 450 ₽"
 * @example formatPrice(12450, "RUB", "en") → "RUB 12,450.00"
 */
export function formatPrice(amount: number, currency: string, locale: string): string {
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency,
    minimumFractionDigits: 0,
    maximumFractionDigits: 2,
  }).format(amount);
}

/**
 * Formats a date using Intl.DateTimeFormat.
 * @example formatDate("2026-03-01", "ru") → "1 мар 2026"
 * @example formatDate("2026-03-01", "de") → "1. März 2026"
 */
export function formatDate(date: string | Date, locale: string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(d);
}

/**
 * Formats a date with time using Intl.DateTimeFormat.
 * @example formatDateTime("2026-03-01T14:30:00", "ru") → "1 мар 2026 г., 14:30"
 */
export function formatDateTime(date: string | Date, locale: string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

/**
 * Formats relative time (e.g. "2 hours ago", "5 minutes ago", "yesterday").
 * Uses Intl.RelativeTimeFormat.
 */
export function formatRelativeTime(date: string | Date, locale: string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  const now = new Date();
  const diffMs = d.getTime() - now.getTime();
  const diffSec = Math.round(diffMs / 1000);
  const diffMin = Math.round(diffSec / 60);
  const diffHour = Math.round(diffMin / 60);
  const diffDay = Math.round(diffHour / 24);

  const rtf = new Intl.RelativeTimeFormat(locale, { numeric: "auto" });

  if (Math.abs(diffSec) < 60) {
    return rtf.format(diffSec, "second");
  }
  if (Math.abs(diffMin) < 60) {
    return rtf.format(diffMin, "minute");
  }
  if (Math.abs(diffHour) < 24) {
    return rtf.format(diffHour, "hour");
  }
  if (Math.abs(diffDay) < 7) {
    return rtf.format(diffDay, "day");
  }
  return formatDate(d, locale);
}

/**
 * Short date + time format for timelines (e.g. "5 мар, 14:32").
 */
export function formatShortDateTime(date: string | Date, locale: string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
  }).format(d);
}

/**
 * Short date format for charts (day + month).
 */
export function formatChartDate(date: string | Date, locale: string): string {
  const d = typeof date === "string" ? new Date(date) : date;
  return new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
  }).format(d);
}

/**
 * Period range format for digests (e.g. "1–7 мар 2026").
 */
export function formatPeriodRange(
  periodStart: string | Date,
  periodEnd: string | Date,
  locale: string
): string {
  const start = typeof periodStart === "string" ? new Date(periodStart) : periodStart;
  const end = typeof periodEnd === "string" ? new Date(periodEnd) : periodEnd;
  const fmt = new Intl.DateTimeFormat(locale, {
    day: "numeric",
    month: "short",
    year: "numeric",
  });
  const startParts = fmt.formatToParts(start);
  const endParts = fmt.formatToParts(end);
  const getPart = (parts: Intl.DateTimeFormatPart[], type: string) =>
    parts.find((p) => p.type === type)?.value ?? "";
  const startDay = getPart(startParts, "day");
  const endDay = getPart(endParts, "day");
  const startMonth = getPart(startParts, "month");
  const endMonth = getPart(endParts, "month");
  const startYear = getPart(startParts, "year");
  const endYear = getPart(endParts, "year");
  if (startMonth === endMonth && startYear === endYear && startDay !== endDay) {
    return `${startDay}–${endDay} ${endMonth} ${endYear}`.trim();
  }
  return `${fmt.format(start)} – ${fmt.format(end)}`;
}
