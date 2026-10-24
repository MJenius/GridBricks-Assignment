import type { Interval } from '../api/types';
import { fmtDateTime, fmtHours, fmtMW, fmtTime } from '../lib/format';

interface Props {
  selected: Interval | null;
  onSelect: (interval: Interval) => void;
  intervals: Interval[];
  onOpenRevisions?: () => void;
}

export function IntervalInspector({ selected, onOpenRevisions }: Props) {
  if (!selected) {
    return (
      <div className="inspector empty-inspector">
        <p className="muted">Click any interval on the chart or select from the table to inspect forecast provenance and eligibility.</p>
      </div>
    );
  }

  const isOver = (selected.error_mw ?? 0) > 0;
  const isUnder = (selected.error_mw ?? 0) < 0;

  return (
    <div className="inspector" data-testid="interval-inspector">
      <div className="inspector-header">
        <div>
          <h4>Delivery Interval {fmtTime(selected.start_time)}</h4>
          <span className="small muted">{fmtDateTime(selected.start_time)}</span>
        </div>
        <span className={`status-pill status-${selected.status}`}>
          {selected.status === 'matched' ? 'Matched Pair' : selected.status.replace('_', ' ')}
        </span>
      </div>

      <div className="inspector-grid">
        <div className="inspector-cell">
          <span className="cell-label">Actual Generation</span>
          <span className="cell-value">{fmtMW(selected.actual_mw)} MW</span>
          <span className="cell-hint">FUELHH (Wind)</span>
        </div>
        <div className="inspector-cell">
          <span className="cell-label">Selected Forecast</span>
          <span className="cell-value">{fmtMW(selected.forecast_mw)} MW</span>
          <span className="cell-hint">WINDFOR eligible vintage</span>
        </div>
        <div className="inspector-cell">
          <span className="cell-label">Forecast Error (F − A)</span>
          <span className={`cell-value ${isOver ? 'tone-over' : isUnder ? 'tone-under' : ''}`}>
            {fmtMW(selected.error_mw, { signed: true })} MW
          </span>
          <span className="cell-hint">{isOver ? 'Over-forecast (Procured excess)' : isUnder ? 'Under-forecast (Procured shortfall)' : 'Exact'}</span>
        </div>
        <div className="inspector-cell">
          <span className="cell-label">Vintage Publish Time</span>
          <span className="cell-value">{fmtDateTime(selected.publish_time)}</span>
          <span className="cell-hint">Lead horizon: {fmtHours(selected.horizon_hours)}</span>
        </div>
      </div>

      <div className="inspector-actions">
        {onOpenRevisions && (
          <button type="button" className="btn secondary small" onClick={onOpenRevisions}>
            Inspect all vintages for this day →
          </button>
        )}
      </div>
    </div>
  );
}
