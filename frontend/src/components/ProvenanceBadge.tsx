import { useState } from 'react';
import type { Provenance } from '../api/types';
import { fmtUtc } from '../lib/format';

const SOURCE_LABEL: Record<string, string> = {
  snapshot: 'Elexon historical snapshot',
  live: 'Elexon live query',
  fixture: 'TEST FIXTURE — not real data',
};

export function ProvenanceBadge({ provenance }: { provenance: Provenance | undefined }) {
  const [open, setOpen] = useState(false);
  if (!provenance) return <span className="prov prov-pending">Data source: loading…</span>;
  const kind = provenance.source;
  return (
    <div className="prov-wrap">
      <button
        type="button"
        className={`prov prov-${kind}`}
        aria-expanded={open}
        aria-controls="prov-panel"
        onClick={() => setOpen((o) => !o)}
      >
        <span className="prov-dot" aria-hidden="true" />
        {SOURCE_LABEL[kind] ?? kind}
        <span className="prov-time">retrieved {fmtUtc(provenance.retrieved_at)}</span>
      </button>
      {open && (
        <div id="prov-panel" className="prov-panel" role="dialog" aria-label="Data provenance">
          <h3>Data provenance</h3>
          <dl>
            <dt>Source</dt>
            <dd>{provenance.label}</dd>
            <dt>Retrieved</dt>
            <dd>{fmtUtc(provenance.retrieved_at)}</dd>
            <dt>Loaded by API</dt>
            <dd>{fmtUtc(provenance.loaded_at)}</dd>
            <dt>WINDFOR records</dt>
            <dd>
              {provenance.forecast_records.toLocaleString('en-GB')} across {provenance.publish_times} publications
            </dd>
            <dt>FUELHH WIND records</dt>
            <dd>{provenance.actual_records.toLocaleString('en-GB')}</dd>
            {Object.entries(provenance.quality).map(([k, q]) => (
              <div key={k} className="dl-row">
                <dt>{k} quality</dt>
                <dd className="mono small">
                  recv {q.received} · ok {q.accepted} · invalid {q.invalid} · dup {q.exact_duplicates} · conflict{' '}
                  {q.conflicting_duplicates} · superseded {q.superseded}
                </dd>
              </div>
            ))}
          </dl>
          <div className="small muted">Queries</div>
          <ul className="endpoint-list">
            {provenance.endpoints.map((e) => (
              <li key={e} className="mono small">
                {e}
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
