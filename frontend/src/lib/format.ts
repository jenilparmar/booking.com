// Fixed locale + timezone so server and client render identical strings (no hydration drift).
export const LOCALE = "en-AU";
export const BUSINESS_TZ = "Australia/Sydney";

const dateFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: BUSINESS_TZ,
  day: "numeric",
  month: "short",
  year: "numeric",
});
const dateTimeFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: BUSINESS_TZ,
  day: "numeric",
  month: "short",
  year: "numeric",
  hour: "2-digit",
  minute: "2-digit",
  hour12: false,
});
const shortDateFmt = new Intl.DateTimeFormat(LOCALE, {
  timeZone: BUSINESS_TZ,
  day: "numeric",
  month: "short",
});
// Week keys are plain calendar dates; format them in UTC so the date never shifts.
const weekFmt = new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", day: "numeric", month: "short" });

export const NA = "N/A";

export function formatDate(iso: string | null | undefined): string {
  return iso ? dateFmt.format(new Date(iso)) : NA;
}

export function formatDateTime(iso: string | null | undefined): string {
  return iso ? dateTimeFmt.format(new Date(iso)) : NA;
}

export function formatShortDate(iso: string | null | undefined): string {
  return iso ? shortDateFmt.format(new Date(iso)) : NA;
}

export function formatWeek(weekStart: string): string {
  return weekFmt.format(new Date(`${weekStart}T00:00:00Z`));
}

export function formatPeriod(p: { start: string; end: string } | null | undefined): string {
  if (!p) return NA;
  return `${formatShortDate(p.start)} – ${formatDateTime(p.end)}`;
}

export function formatRating(v: number | null | undefined): string {
  return v === null || v === undefined ? NA : v.toFixed(1);
}

export function formatPct(v: number | null | undefined, digits = 1): string {
  return v === null || v === undefined ? NA : `${v.toFixed(digits)}%`;
}

export function formatSigned(v: number | null | undefined, digits = 1, suffix = ""): string {
  if (v === null || v === undefined) return NA;
  const s = v.toFixed(digits);
  return `${v > 0 ? "+" : v < 0 ? "" : "±"}${s}${suffix}`;
}

export function plural(n: number, word: string, pluralWord = `${word}s`): string {
  return `${n} ${n === 1 ? word : pluralWord}`;
}
