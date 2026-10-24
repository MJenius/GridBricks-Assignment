import { useMemo } from 'react';
import { useDeliveryDay } from '../api/hooks';
import { EChart, type ChartClick } from '../components/EChart';
import { IntervalInspector } from '../components/IntervalInspector';
import { MetricStrip } from '../components/MetricStrip';
import { Notice } from '../components/States';
import { TimingControls } from '../components/TimingControls';
import { cockpitOption, slotAt } from '../lib/charts';
import { fmtDateTime, fmtMW, fmtTime } from '../lib/format';
import type { DeskState } from '../state/useDeskState';
import { addDays } from '../lib/dates';

interface Props {
  state: DeskState;
  update: (patch: Partial<DeskState>) => void;
}

export function DecisionCockpit({ state, update }: Props) {
  const deliveryDate = addDays(state.decision, state.lead);
  const timing = useMemo(() => ({ cutoff: state.cutoff, lead: state.lead }), [state.cutoff, state.lead]);

  const { data, isLoading, error, refetch } = useDeliveryDay(deliveryDate, timing);

  const selectedInterval = useMemo(() => {
    if (!data || !state.t) return null;
    return data.intervals.find((i) => i.start_time === state.t) ?? null;
  }, [data, state.t]);

  const chartOpt = useMemo(() => {
    if (!data) return null;
    return cockpitOption(data, state.t);
  }, [data, state.t]);

  const handleChartClick = (e: ChartClick) => {
    if (!data) return;
    const slot = slotAt(data, e.dataIndex);
    if (slot?.interval) {
      update({ t: slot.interval.start_time });
    }
  };

  return (
    <div className="workspace-view cockpit-view">
      <header className="workspace-header">
        <div className="workspace-title">
          <h2>Decision Cockpit</h2>
          <p className="subtitle">
            Point-in-time wind forecast available at decision cutoff vs subsequent actual delivery.
          </p>
        </div>
        <TimingControls state={state} update={update} showDate={true} />
      </header>

      {data?.provenance.warnings && data.provenance.warnings.length > 0 && (
        <Notice tone="warn">
          {data.provenance.warnings.map((w, i) => (
            <div key={i}>{w}</div>
          ))}
        </Notice>
      )}

      {isLoading && <div className="state state-loading">Loading decision day replay...</div>}
      {error && (
        <div className="state state-error">
          <p>Failed to load delivery day: {(error as Error).message}</p>
          <button className="btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <MetricStrip metrics={data.metrics} coverage={data.coverage} />

          <div className="chart-card">
            <div className="chart-card-header">
              <div>
                <h3>Day-Ahead Profile Replay</h3>
                <span className="small muted">
                  Decision cut-off: {fmtDateTime(data.cutoff_utc)} ({state.cutoff} Europe/London)
                </span>
              </div>
              <div className="chart-actions">
                <span className="badge">Delivery: {data.delivery_date}</span>
              </div>
            </div>

            {chartOpt && (
              <EChart
                option={chartOpt}
                height={420}
                ariaLabel="Decision time forecast vs actual generation time series"
                onClick={handleChartClick}
              />
            )}
          </div>

          <div className="cockpit-lower-grid">
            <div className="table-card">
              <div className="table-header">
                <h3>Delivery Intervals</h3>
                <span className="small muted">Hourly settlement intervals (MW)</span>
              </div>
              <div className="table-scroll">
                <table className="data-table" aria-label="Hourly delivery intervals">
                  <thead>
                    <tr>
                      <th>Delivery (UK)</th>
                      <th>Eligible Forecast</th>
                      <th>Actual</th>
                      <th>Error</th>
                      <th>Published</th>
                      <th>Status</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.intervals.map((inv) => {
                      const isSel = state.t === inv.start_time;
                      return (
                        <tr
                          key={inv.start_time}
                          className={`clickable-row ${isSel ? 'selected-row' : ''}`}
                          onClick={() => update({ t: inv.start_time })}
                        >
                          <td className="mono">{fmtTime(inv.start_time)}</td>
                          <td className="mono">{fmtMW(inv.forecast_mw)}</td>
                          <td className="mono">{fmtMW(inv.actual_mw)}</td>
                          <td
                            className={`mono ${
                              (inv.error_mw ?? 0) > 0 ? 'tone-over' : (inv.error_mw ?? 0) < 0 ? 'tone-under' : ''
                            }`}
                          >
                            {fmtMW(inv.error_mw, { signed: true })}
                          </td>
                          <td className="small muted">{fmtTime(inv.publish_time ?? '')}</td>
                          <td>
                            <span className={`status-pill small status-${inv.status}`}>{inv.status}</span>
                          </td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            <IntervalInspector
              selected={selectedInterval}
              intervals={data.intervals}
              onSelect={(inv) => update({ t: inv.start_time })}
              onOpenRevisions={() => update({ view: 'revisions' })}
            />
          </div>
        </>
      )}
    </div>
  );
}
