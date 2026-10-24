import type { ReactNode } from 'react';
import type { Coverage, Metric, Metrics } from '../api/types';
import { biasDirection, fmtMW, fmtPct } from '../lib/format';

interface CardProps {
  label: string;
  value: string;
  unit?: string;
  hint?: ReactNode;
  unavailable?: string | null;
  tone?: 'default' | 'over' | 'under' | 'warn';
}

export function MetricCard({ label, value, unit, hint, unavailable, tone = 'default' }: CardProps) {
  return (
    <div className={`metric-card tone-${tone}`} role="group" aria-label={label}>
      <div className="metric-label">{label}</div>
      {unavailable ? (
        <div className="metric-unavailable" title={unavailable}>
          <span className="metric-value muted">n/a</span>
          <span className="metric-hint">{unavailable}</span>
        </div>
      ) : (
        <>
          <div className="metric-value">
            {value}
            {unit && <span className="metric-unit">{unit}</span>}
          </div>
          {hint && <div className="metric-hint">{hint}</div>}
        </>
      )}
    </div>
  );
}

function mw(m: Metric, signed = false) {
  return { value: fmtMW(m.value, { signed }), unavailable: m.value === null ? (m.reason ?? 'Unavailable') : null };
}

export function MetricStrip({ metrics, coverage }: { metrics: Metrics; coverage: Coverage }) {
  const bias = metrics.bias.value;
  const covTone = coverage.matched_pct === null || coverage.matched_pct < 100 ? 'warn' : 'default';
  return (
    <div className="metric-strip">
      <MetricCard label="MAE" unit="MW" {...mw(metrics.mae)} hint="Mean absolute error" />
      <MetricCard label="RMSE" unit="MW" {...mw(metrics.rmse)} hint="Penalises large misses" />
      <MetricCard
        label="Mean bias"
        unit="MW"
        {...mw(metrics.bias, true)}
        tone={bias === null ? 'default' : bias > 0 ? 'over' : bias < 0 ? 'under' : 'default'}
        hint={bias === null ? undefined : `Forecast − actual · ${biasDirection(bias)}`}
      />
      <MetricCard
        label="WAPE"
        value={fmtPct(metrics.wape.value)}
        unavailable={metrics.wape.value === null ? (metrics.wape.reason ?? 'Unavailable') : null}
        hint="Σ|error| ÷ Σ actual"
      />
      <MetricCard
        label="Matched coverage"
        value={`${coverage.matched}/${coverage.expected}`}
        tone={covTone}
        hint={`${fmtPct(coverage.matched_pct)} of hourly intervals · F ${coverage.forecast_available} · A ${coverage.actual_available}`}
      />
    </div>
  );
}
