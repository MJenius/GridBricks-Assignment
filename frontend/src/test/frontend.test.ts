import { describe, it, expect } from 'vitest';
import { fmtMW, fmtPct, fmtHours, biasDirection } from '../lib/format';
import { addDays, clampDecision, isValidCutoff } from '../lib/dates';
import { parseState, serializeState } from '../state/useDeskState';

describe('format utilities', () => {
  it('formats MW values cleanly', () => {
    expect(fmtMW(1234.56)).toBe('1,235');
    expect(fmtMW(-500, { signed: true })).toBe('−500');
    expect(fmtMW(500, { signed: true })).toBe('+500');
    expect(fmtMW(null)).toBe('—');
  });

  it('formats percentages and hours', () => {
    expect(fmtPct(12.345)).toBe('12.3%');
    expect(fmtPct(null)).toBe('—');
    expect(fmtHours(9.5)).toBe('9.5 h');
  });

  it('computes bias direction', () => {
    expect(biasDirection(100)).toBe('over-forecast');
    expect(biasDirection(-100)).toBe('under-forecast');
    expect(biasDirection(0)).toBe('unbiased');
  });
});

describe('date utilities', () => {
  it('adds days reliably across calendar dates', () => {
    expect(addDays('2026-01-01', 1)).toBe('2026-01-02');
    expect(addDays('2026-01-31', 1)).toBe('2026-02-01');
  });

  it('clamps decision dates to January 2026 scope', () => {
    expect(clampDecision('2025-12-31')).toBe('2026-01-01');
    expect(clampDecision('2026-02-15')).toBe('2026-01-31');
    expect(clampDecision('2026-01-15')).toBe('2026-01-15');
  });

  it('validates cutoff format', () => {
    expect(isValidCutoff('15:30')).toBe(true);
    expect(isValidCutoff('24:00')).toBe(false);
    expect(isValidCutoff('invalid')).toBe(false);
  });
});

describe('state serialization', () => {
  it('round-trips desk state in URL query string', () => {
    const original = parseState('?view=accuracy&decision=2026-01-10&cutoff=12:00&lead=1');
    expect(original.view).toBe('accuracy');
    expect(original.decision).toBe('2026-01-10');
    expect(original.cutoff).toBe('12:00');

    const serialized = serializeState(original);
    expect(serialized).toContain('view=accuracy');
    expect(serialized).toContain('decision=2026-01-10');
    expect(serialized).toContain('cutoff=12%3A00');
  });
});
