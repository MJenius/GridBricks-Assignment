import { useCallback, useSyncExternalStore } from 'react';
import { clampDecision, DECISION_END, DECISION_START, DEFAULT_CUTOFF, DEFAULT_LEAD, isValidCutoff } from '../lib/dates';

export type View = 'cockpit' | 'revisions' | 'accuracy';

/** Shared, URL-addressable filter state. Delivery date is derived (decision + lead), never stored. */
export interface DeskState {
  view: View;
  decision: string;
  cutoff: string;
  lead: number;
  from: string;
  to: string;
  /** Selected interval start (ISO UTC) */
  t: string | null;
  /** Selected vintage publish time (ISO UTC) in the revision explorer */
  pub: string | null;
}

const VIEWS: View[] = ['cockpit', 'revisions', 'accuracy'];

export function parseState(search: string): DeskState {
  const p = new URLSearchParams(search);
  const view = p.get('view') as View | null;
  const cutoff = p.get('cutoff') ?? DEFAULT_CUTOFF;
  const lead = Number(p.get('lead') ?? DEFAULT_LEAD);
  let from = clampDecision(p.get('from') ?? DECISION_START);
  let to = clampDecision(p.get('to') ?? DECISION_END);
  if (to < from) [from, to] = [to, from];
  return {
    view: view && VIEWS.includes(view) ? view : 'cockpit',
    decision: clampDecision(p.get('decision') ?? DECISION_START),
    cutoff: isValidCutoff(cutoff) ? cutoff : DEFAULT_CUTOFF,
    lead: lead === 1 || lead === 2 ? lead : DEFAULT_LEAD,
    from,
    to,
    t: p.get('t'),
    pub: p.get('pub'),
  };
}

export function serializeState(s: DeskState): string {
  const p = new URLSearchParams();
  p.set('view', s.view);
  p.set('decision', s.decision);
  p.set('cutoff', s.cutoff);
  p.set('lead', String(s.lead));
  p.set('from', s.from);
  p.set('to', s.to);
  if (s.t) p.set('t', s.t);
  if (s.pub) p.set('pub', s.pub);
  return `?${p.toString()}`;
}

const listeners = new Set<() => void>();
function subscribe(cb: () => void) {
  listeners.add(cb);
  window.addEventListener('popstate', cb);
  return () => {
    listeners.delete(cb);
    window.removeEventListener('popstate', cb);
  };
}
const getSearch = () => window.location.search;

export function useDeskState(): [DeskState, (patch: Partial<DeskState>) => void] {
  const search = useSyncExternalStore(subscribe, getSearch, getSearch);
  const state = parseState(search);
  const update = useCallback((patch: Partial<DeskState>) => {
    const next = { ...parseState(window.location.search), ...patch };
    // Changing the day or timing invalidates interval / vintage selections.
    if ('decision' in patch || 'cutoff' in patch || 'lead' in patch) {
      if (!('t' in patch)) next.t = null;
      if (!('pub' in patch)) next.pub = null;
    }
    const url = serializeState(next);
    if (url !== window.location.search) {
      window.history.pushState(null, '', url);
      listeners.forEach((l) => l());
    }
  }, []);
  return [state, update];
}
