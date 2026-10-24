import { addDays, CUTOFF_OPTIONS, DECISION_END, DECISION_START, DEFAULT_CUTOFF, DEFAULT_LEAD } from '../lib/dates';
import { fmtDay } from '../lib/format';
import type { DeskState } from '../state/useDeskState';

interface Props {
  state: DeskState;
  update: (patch: Partial<DeskState>) => void;
  /** Show the decision/delivery date picker (hidden on the monthly view). */
  showDate?: boolean;
}

export function TimingControls({ state, update, showDate = true }: Props) {
  const delivery = addDays(state.decision, state.lead);
  const isDefault = state.cutoff === DEFAULT_CUTOFF && state.lead === DEFAULT_LEAD;
  return (
    <div className="controls" role="group" aria-label="Decision timing">
      {showDate && (
        <div className="control">
          <label htmlFor="decision-date">Decision date</label>
          <div className="date-stepper">
            <button
              type="button"
              className="btn icon"
              aria-label="Previous decision date"
              disabled={state.decision <= DECISION_START}
              onClick={() => update({ decision: addDays(state.decision, -1) })}
            >
              ‹
            </button>
            <input
              id="decision-date"
              type="date"
              min={DECISION_START}
              max={DECISION_END}
              value={state.decision}
              onChange={(e) => e.target.value && update({ decision: e.target.value })}
            />
            <button
              type="button"
              className="btn icon"
              aria-label="Next decision date"
              disabled={state.decision >= DECISION_END}
              onClick={() => update({ decision: addDays(state.decision, 1) })}
            >
              ›
            </button>
          </div>
        </div>
      )}
      {showDate && (
        <div className="control derived" aria-live="polite">
          <span className="control-label">Delivery date</span>
          <span className="derived-value" data-testid="delivery-date">
            {fmtDay(delivery)}
          </span>
        </div>
      )}
      <div className="control">
        <label htmlFor="cutoff">Decision cutoff</label>
        <div className="inline">
          <select id="cutoff" value={state.cutoff} onChange={(e) => update({ cutoff: e.target.value })}>
            {CUTOFF_OPTIONS.map((c) => (
              <option key={c} value={c}>
                {c}
              </option>
            ))}
          </select>
          <span className="tz-chip" title="All times are interpreted in Europe/London (GMT in January)">
            Europe/London
          </span>
        </div>
      </div>
      <div className="control">
        <label htmlFor="lead">Decision → delivery</label>
        <select id="lead" value={state.lead} onChange={(e) => update({ lead: Number(e.target.value) })}>
          <option value={1}>D−1 (day-ahead)</option>
          <option value={2}>D−2</option>
        </select>
      </div>
      <div className="control assumption">
        {isDefault ? (
          <span className="tag tag-assumption" title="Not a market rule; configurable">
            Illustrative default cutoff
          </span>
        ) : (
          <button type="button" className="btn ghost" onClick={() => update({ cutoff: DEFAULT_CUTOFF, lead: DEFAULT_LEAD })}>
            Reset to 15:30 D−1
          </button>
        )}
      </div>
    </div>
  );
}
