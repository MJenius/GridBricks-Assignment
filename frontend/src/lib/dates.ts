/** Calendar-date arithmetic on YYYY-MM-DD strings (no timezone involvement). */

export const DECISION_START = '2026-01-01';
export const DECISION_END = '2026-01-31';
export const DEFAULT_CUTOFF = '15:30';
export const DEFAULT_LEAD = 1;

export function addDays(isoDate: string, days: number): string {
  const d = new Date(`${isoDate}T00:00:00Z`);
  d.setUTCDate(d.getUTCDate() + days);
  return d.toISOString().slice(0, 10);
}

export function clampDecision(isoDate: string): string {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(isoDate) || Number.isNaN(Date.parse(isoDate))) return DECISION_START;
  if (isoDate < DECISION_START) return DECISION_START;
  if (isoDate > DECISION_END) return DECISION_END;
  return isoDate;
}

export function isValidCutoff(value: string): boolean {
  const m = /^(\d{2}):(\d{2})$/.exec(value);
  return !!m && Number(m[1]) <= 23 && Number(m[2]) <= 59;
}

/** Cutoff options every 30 minutes, 00:00–23:30. */
export const CUTOFF_OPTIONS: string[] = Array.from({ length: 48 }, (_, i) => {
  const h = String(Math.floor(i / 2)).padStart(2, '0');
  return `${h}:${i % 2 ? '30' : '00'}`;
});
