import { useMemo, useState } from 'react';
import { exportCsvUrl } from '../api/client';
import { useAnalysis } from '../api/hooks';
import { EChart, type ChartClick } from '../components/EChart';
import { MetricStrip } from '../components/MetricStrip';
import { TimingControls } from '../components/TimingControls';
import { dailyOption, heatmapOption, histogramOption } from '../lib/charts';
import { fmtMW, fmtTime } from '../lib/format';
import type { DeskState } from '../state/useDeskState';

interface Props {
  state: DeskState;
  update: (patch: Partial<DeskState>) => void;
}

export function AccuracyAnalysis({ state, update }: Props) {
  const [activeTab, setActiveTab] = useState<'daily' | 'distribution' | 'heatmap' | 'misses'>('daily');

  const timing = useMemo(() => ({ cutoff: state.cutoff, lead: state.lead }), [state.cutoff, state.lead]);
  const { data, isLoading, error, refetch } = useAnalysis(state.from, state.to, timing);

  const dailyOpt = useMemo(() => {
    if (!data) return null;
    return dailyOption(data, state.decision);
  }, [data, state.decision]);

  const histOpt = useMemo(() => {
    if (!data) return null;
    return histogramOption(data);
  }, [data]);

  const heatOpt = useMemo(() => {
    if (!data) return null;
    return heatmapOption(data);
  }, [data]);

  const handleDailyClick = (e: ChartClick) => {
    if (!data) return;
    const d = data.daily[e.dataIndex];
    if (d) {
      update({ decision: d.decision_date, view: 'cockpit' });
    }
  };

  const csvUrl = exportCsvUrl(state.from, state.to, timing);

  return (
    <div className="workspace-view accuracy-view">
      <header className="workspace-header">
        <div className="workspace-title">
          <h2>Accuracy & Procurement Risk Analysis</h2>
          <p className="subtitle">
            Quantitative assessment of national wind forecast performance across decision dates.
          </p>
        </div>
        <div className="header-actions">
          <TimingControls state={state} update={update} showDate={false} />
          <a
            href={csvUrl}
            download
            className="btn primary export-btn"
            title="Download complete interval-level CSV"
          >
            Export CSV
          </a>
        </div>
      </header>

      {isLoading && <div className="state state-loading">Loading monthly performance analytics...</div>}
      {error && (
        <div className="state state-error">
          <p>Failed to load analysis: {(error as Error).message}</p>
          <button className="btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <MetricStrip metrics={data.metrics} coverage={data.coverage} />

          <div className="analysis-tabs">
            <button
              className={`tab-btn ${activeTab === 'daily' ? 'active' : ''}`}
              onClick={() => setActiveTab('daily')}
            >
              Daily MAE & Bias Trends
            </button>
            <button
              className={`tab-btn ${activeTab === 'distribution' ? 'active' : ''}`}
              onClick={() => setActiveTab('distribution')}
            >
              Error Distribution
            </button>
            <button
              className={`tab-btn ${activeTab === 'heatmap' ? 'active' : ''}`}
              onClick={() => setActiveTab('heatmap')}
            >
              Settlement Period Heatmap
            </button>
            <button
              className={`tab-btn ${activeTab === 'misses' ? 'active' : ''}`}
              onClick={() => setActiveTab('misses')}
            >
              Largest Forecast Misses
            </button>
          </div>

          <div className="tab-container">
            {activeTab === 'daily' && (
              <div className="chart-card">
                <div className="chart-card-header">
                  <div>
                    <h3>Daily Accuracy Trends</h3>
                    <span className="small muted">
                      Bars: Daily MAE (MW) | Line: Mean Signed Bias (MW). Click any day to jump to Decision Cockpit.
                    </span>
                  </div>
                </div>
                {dailyOpt && (
                  <EChart
                    option={dailyOpt}
                    height={440}
                    ariaLabel="Daily MAE and bias chart"
                    onClick={handleDailyClick}
                  />
                )}
              </div>
            )}

            {activeTab === 'distribution' && (
              <div className="chart-card">
                <div className="chart-card-header">
                  <div>
                    <h3>Forecast Error Distribution (MW)</h3>
                    <span className="small muted">
                      P05: {fmtMW(data.error_percentiles.p05_mw, { signed: true })} MW | Median:{' '}
                      {fmtMW(data.error_percentiles.p50_mw, { signed: true })} MW | P95:{' '}
                      {fmtMW(data.error_percentiles.p95_mw, { signed: true })} MW
                    </span>
                  </div>
                </div>
                {histOpt && (
                  <EChart
                    option={histOpt}
                    height={440}
                    ariaLabel="Forecast error histogram"
                  />
                )}
              </div>
            )}

            {activeTab === 'heatmap' && (
              <div className="chart-card">
                <div className="chart-card-header">
                  <div>
                    <h3>Delivery Day vs Hour Error Heatmap</h3>
                    <span className="small muted">
                      Red: Over-forecast (Excess wind) | Blue: Under-forecast (Shortfall)
                    </span>
                  </div>
                </div>
                {heatOpt && (
                  <EChart
                    option={heatOpt}
                    height={500}
                    ariaLabel="Delivery Day vs Hour Error Heatmap"
                  />
                )}
              </div>
            )}

            {activeTab === 'misses' && (
              <div className="table-card">
                <div className="table-header">
                  <h3>Top 15 Absolute Forecast Misses</h3>
                  <span className="small muted">Largest magnitude forecasting errors during the month</span>
                </div>
                <div className="table-scroll">
                  <table className="data-table" aria-label="Top forecast misses">
                    <thead>
                      <tr>
                        <th>Delivery Date</th>
                        <th>Target Time (UK)</th>
                        <th>Eligible Forecast</th>
                        <th>Actual Wind</th>
                        <th>Absolute Miss</th>
                        <th>Signed Error (F − A)</th>
                        <th>Action</th>
                      </tr>
                    </thead>
                    <tbody>
                      {data.top_misses.map((m) => (
                        <tr key={m.start_time}>
                          <td className="mono">{m.delivery_date}</td>
                          <td className="mono">{fmtTime(m.start_time)}</td>
                          <td className="mono">{fmtMW(m.forecast_mw)} MW</td>
                          <td className="mono">{fmtMW(m.actual_mw)} MW</td>
                          <td className="mono font-bold">{fmtMW(m.abs_error_mw)} MW</td>
                          <td
                            className={`mono ${
                              (m.error_mw ?? 0) > 0 ? 'tone-over' : (m.error_mw ?? 0) < 0 ? 'tone-under' : ''
                            }`}
                          >
                            {fmtMW(m.error_mw, { signed: true })} MW
                          </td>
                          <td>
                            <button
                              type="button"
                              className="btn ghost small"
                              onClick={() => {
                                update({ decision: m.delivery_date, view: 'cockpit', t: m.start_time });
                              }}
                            >
                              Inspect Cockpit →
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
