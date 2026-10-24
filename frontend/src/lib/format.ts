/** Formatting helpers. All wall-clock display is Europe/London. */

export const TZ = 'Europe/London';

const mwFmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 0 });
const pctFmt = new Intl.NumberFormat('en-GB', { maximumFractionDigits: 1, minimumFractionDigits: 1 });

export const DASH = '—';

export function fmtMW(value: number | null | undefined, opts: { signed?: boolean } = {}): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  const rounded = Math.round(value);
  const body = mwFmt.format(Math.abs(rounded));
  if (opts.signed) return `${rounded > 0 ? '+' : rounded < 0 ? '−' : '±'}${body}`;
  return rounded < 0 ? `−${body}` : body;
}

export function fmtPct(value: number | null | undefined): string {
  if (value === null || value === undefined || !Number.isFinite(value)) return DASH;
  return `${pctFmt.format(value)}%`;
}

export function fmtHours(value: number | null | undefined): string {
  if (value === null || value === undefined) return DASH;
  return `${value.toFixed(1)} h`;
}

const timeFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, hour: '2-digit', minute: '2-digit', hour12: false });
const dateTimeFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: TZ,
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  hour: '2-digit',
  minute: '2-digit',
  hour12: false,
});
const dayFmt = new Intl.DateTimeFormat('en-GB', {
  timeZone: 'UTC',
  weekday: 'short',
  day: 'numeric',
  month: 'short',
  year: 'numeric',
});
const shortDayFmt = new Intl.DateTimeFormat('en-GB', { timeZone: 'UTC', day: 'numeric', month: 'short' });
const tzNameFmt = new Intl.DateTimeFormat('en-GB', { timeZone: TZ, timeZoneName: 'short' });

export function fmtTime(iso: string): string {
  return timeFmt.format(new Date(iso));
}

export function fmtDateTime(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return dateTimeFmt.format(new Date(iso));
}

/** UK zone abbreviation (GMT/BST) for an instant. */
export function tzAbbrev(iso: string): string {
  return tzNameFmt.formatToParts(new Date(iso)).find((p) => p.type === 'timeZoneName')?.value ?? 'UK';
}

/** Format a calendar date string (YYYY-MM-DD) without timezone shifts. */
export function fmtDay(isoDate: string): string {
  return dayFmt.format(new Date(`${isoDate}T00:00:00Z`));
}

export function fmtShortDay(isoDate: string): string {
  return shortDayFmt.format(new Date(`${isoDate}T00:00:00Z`));
}

export function fmtUtc(iso: string | null | undefined): string {
  if (!iso) return DASH;
  return `${new Date(iso).toISOString().slice(0, 16).replace('T', ' ')} UTC`;
}

export function biasDirection(bias: number | null | undefined): string {
  if (bias === null || bias === undefined) return '';
  if (bias > 0) return 'over-forecast';
  if (bias < 0) return 'under-forecast';
  return 'unbiased';
}
