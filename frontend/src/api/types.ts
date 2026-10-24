/** Mirrors backend/app/schemas/api.py. Units: MW, %, hours. Times are ISO-8601 strings. */

export type IntervalStatus = 'matched' | 'missing_forecast' | 'missing_actual' | 'missing_both';

export interface Metric {
  value: number | null;
  unit: string;
  reason: string | null;
}

export interface Metrics {
  mae: Metric;
  rmse: Metric;
  bias: Metric;
  wape: Metric;
  max_abs_error: Metric;
  matched: number;
}

export interface Coverage {
  expected: number;
  forecast_available: number;
  actual_available: number;
  matched: number;
  forecast_pct: number | null;
  actual_pct: number | null;
  matched_pct: number | null;
}

export interface DecisionContext {
  timezone: 'Europe/London';
  cutoff_local: string;
  lead_days: number;
  is_illustrative_default: boolean;
  rule: string;
}

export interface Provenance {
  source: 'snapshot' | 'live' | 'fixture' | string;
  label: string;
  retrieved_at: string | null;
  loaded_at: string;
  endpoints: string[];
  quality: Record<string, Record<string, number>>;
  warnings: string[];
  forecast_records: number;
  actual_records: number;
  publish_times: number;
}

export interface Interval {
  delivery_date: string;
  start_time: string;
  start_local: string;
  forecast_mw: number | null;
  publish_time: string | null;
  horizon_hours: number | null;
  actual_mw: number | null;
  error_mw: number | null;
  abs_error_mw: number | null;
  status: IntervalStatus;
}

export interface ActualPoint {
  start_time: string;
  generation_mw: number;
  settlement_period: number | null;
}

export interface DeliveryDay {
  delivery_date: string;
  decision_date: string;
  cutoff_utc: string;
  cutoff_local: string;
  context: DecisionContext;
  metrics: Metrics;
  coverage: Coverage;
  vintages_used: string[];
  intervals: Interval[];
  actual_series: ActualPoint[];
  provenance: Provenance;
}

export interface DailyStat {
  delivery_date: string;
  decision_date: string;
  cutoff_utc: string;
  mae_mw: number | null;
  rmse_mw: number | null;
  bias_mw: number | null;
  wape_pct: number | null;
  mean_actual_mw: number | null;
  mean_forecast_mw: number | null;
  coverage: Coverage;
}

export interface HourStat {
  hour_local: number;
  mae_mw: number | null;
  bias_mw: number | null;
  matched: number;
}

export interface HistogramBin {
  lower_mw: number;
  upper_mw: number;
  count: number;
}

export interface HeatmapCell {
  delivery_date: string;
  hour_local: number;
  error_mw: number | null;
}

export interface Analysis {
  decision_from: string;
  decision_to: string;
  delivery_from: string;
  delivery_to: string;
  context: DecisionContext;
  metrics: Metrics;
  coverage: Coverage;
  daily: DailyStat[];
  by_hour: HourStat[];
  histogram: HistogramBin[];
  histogram_bin_mw: number;
  error_percentiles: { p05_mw: number | null; p50_mw: number | null; p95_mw: number | null };
  top_misses: Interval[];
  heatmap: HeatmapCell[];
  provenance: Provenance;
}

export interface VintagePoint {
  start_time: string;
  generation_mw: number;
}

export interface Vintage {
  publish_time: string;
  eligible: boolean;
  is_decision_vintage: boolean;
  hours_before_delivery_start: number;
  points: VintagePoint[];
  mae_mw: number | null;
  matched: number;
}

export interface Revisions {
  delivery_date: string;
  decision_date: string;
  cutoff_utc: string;
  cutoff_local: string;
  context: DecisionContext;
  vintages: Vintage[];
  decision_intervals: Interval[];
  actual_series: ActualPoint[];
  provenance: Provenance;
}

export interface ApiErrorBody {
  error: { code: string; message: string; request_id?: string | null };
}
