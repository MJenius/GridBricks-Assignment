import { useMemo } from 'react';
import { useRevisions } from '../api/hooks';
import { EChart } from '../components/EChart';
import { Notice } from '../components/States';
import { TimingControls } from '../components/TimingControls';
import { revisionsOption, vintageRole } from '../lib/charts';
import { addDays } from '../lib/dates';
import { fmtDateTime, fmtMW } from '../lib/format';
import type { DeskState } from '../state/useDeskState';

interface Props {
  state: DeskState;
  update: (patch: Partial<DeskState>) => void;
}

export function RevisionExplorer({ state, update }: Props) {
  const deliveryDate = addDays(state.decision, state.lead);
  const timing = useMemo(() => ({ cutoff: state.cutoff, lead: state.lead }), [state.cutoff, state.lead]);

  const { data, isLoading, error, refetch } = useRevisions(deliveryDate, timing);

  const selectedVintage = useMemo(() => {
    if (!data || !state.pub) return null;
    return data.vintages.find((v) => v.publish_time === state.pub) ?? null;
  }, [data, state.pub]);

  const chartOpt = useMemo(() => {
    if (!data) return null;
    return revisionsOption(data, state.pub, state.t);
  }, [data, state.pub, state.t]);

  return (
    <div className="workspace-view revisions-view">
      <header className="workspace-header">
        <div className="workspace-title">
          <h2>Forecast Revision Explorer</h2>
          <p className="subtitle">
            Inspect all publication vintages for the delivery day and verify cutoff eligibility.
          </p>
        </div>
        <TimingControls state={state} update={update} showDate={true} />
      </header>

      {isLoading && <div className="state state-loading">Loading forecast revisions...</div>}
      {error && (
        <div className="state state-error">
          <p>Failed to load revisions: {(error as Error).message}</p>
          <button className="btn" onClick={() => refetch()}>
            Retry
          </button>
        </div>
      )}

      {data && (
        <>
          <div className="callout-card">
            <div className="callout-content">
              <strong>Point-in-Time Cutoff Rule:</strong> Vintages published strictly after{' '}
              <span className="mono">{fmtDateTime(data.cutoff_utc)}</span> were NOT available at the decision cutoff and
              are marked as ineligible. Later vintages are displayed for post-hoc evolution analysis only and never
              influence decision replay metrics.
            </div>
          </div>

          <div className="chart-card">
            <div className="chart-card-header">
              <div>
                <h3>Forecast Evolution by Publication Vintage</h3>
                <span className="small muted">
                  Dashed purple: post-cutoff revisions | Solid amber: eligible decision vintage | Green: actual
                </span>
              </div>
            </div>

            {chartOpt && (
              <EChart
                option={chartOpt}
                height={420}
                ariaLabel="Forecast revisions evolution chart"
              />
            )}
          </div>

          <div className="revisions-split">
            <div className="table-card">
              <div className="table-header">
                <h3>Available Vintages ({data.vintages.length})</h3>
                <span className="small muted">Click a vintage to highlight on the evolution chart</span>
              </div>
              <div className="table-scroll">
                <table className="data-table" aria-label="Available forecast vintages">
                  <thead>
                    <tr>
                      <th>Publish Time (UK)</th>
                      <th>Hours to Delivery</th>
                      <th>Eligibility</th>
                      <th>Retrospective MAE</th>
                      <th>Coverage</th>
                    </tr>
                  </thead>
                  <tbody>
                    {data.vintages.map((v) => {
                      const role = vintageRole(v);
                      const isSel = state.pub === v.publish_time;
                      return (
                        <tr
                          key={v.publish_time}
                          className={`clickable-row ${isSel ? 'selected-row' : ''}`}
                          onClick={() => update({ pub: isSel ? null : v.publish_time })}
                        >
                          <td className="mono">{fmtDateTime(v.publish_time)}</td>
                          <td className="mono">{v.hours_before_delivery_start.toFixed(1)} h</td>
                          <td>
                            {role === 'decision' ? (
                              <span className="tag tag-success">Selected Decision Vintage</span>
                            ) : v.eligible ? (
                              <span className="tag tag-info">Earlier Eligible</span>
                            ) : (
                              <span className="tag tag-warn">Post-Cutoff (Ineligible)</span>
                            )}
                          </td>
                          <td className="mono">{fmtMW(v.mae_mw)} MW</td>
                          <td className="small muted">{v.matched} intervals</td>
                        </tr>
                      );
                    })}
                  </tbody>
                </table>
              </div>
            </div>

            {selectedVintage && (
              <div className="vintage-detail-card">
                <h3>Vintage Detail</h3>
                <dl className="kv-list">
                  <dt>Published At</dt>
                  <dd className="mono">{fmtDateTime(selectedVintage.publish_time)}</dd>
                  <dt>Status</dt>
                  <dd>
                    {selectedVintage.eligible ? (
                      <span className="tone-over">Eligible for decision cutoff</span>
                    ) : (
                      <span className="tone-under">Ineligible (Published after cutoff)</span>
                    )}
                  </dd>
                  <dt>Retrospective MAE</dt>
                  <dd className="mono">{fmtMW(selectedVintage.mae_mw)} MW</dd>
                  <dt>Points Available</dt>
                  <dd className="mono">{selectedVintage.points.length} intervals</dd>
                </dl>
                {!selectedVintage.eligible && (
                  <Notice tone="warn">
                    Warning: This forecast was published after {state.cutoff} UK time on decision day. Substituting this
                    forecast into day-ahead procurement decisions would introduce look-ahead bias!
                  </Notice>
                )}
              </div>
            )}
          </div>
        </>
      )}
    </div>
  );
}
