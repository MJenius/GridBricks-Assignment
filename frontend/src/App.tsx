import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { useDeskState } from './state/useDeskState';
import { DecisionCockpit } from './views/DecisionCockpit';
import { RevisionExplorer } from './views/RevisionExplorer';
import { AccuracyAnalysis } from './views/AccuracyAnalysis';
import { ProvenanceBadge } from './components/ProvenanceBadge';
import { useDeliveryDay } from './api/hooks';
import { addDays } from './lib/dates';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 60_000,
      refetchOnWindowFocus: false,
      retry: 1,
    },
  },
});

function AppContent() {
  const [state, update] = useDeskState();
  const deliveryDate = addDays(state.decision, state.lead);

  // Load delivery day to get top-level provenance badge data
  const { data: dayData } = useDeliveryDay(deliveryDate, { cutoff: state.cutoff, lead: state.lead });

  return (
    <div className="desk-shell">
      <nav className="top-nav" aria-label="Main Navigation">
        <div className="brand">
          <div className="brand-icon" aria-hidden="true">
            💨
          </div>
          <div className="brand-text">
            <span className="brand-name">Wind Desk</span>
            <span className="brand-tagline">Day-Ahead Power Procurement Intelligence</span>
          </div>
        </div>

        <div className="nav-tabs" role="tablist">
          <button
            role="tab"
            aria-selected={state.view === 'cockpit'}
            className={`nav-tab ${state.view === 'cockpit' ? 'active' : ''}`}
            onClick={() => update({ view: 'cockpit' })}
          >
            Decision Cockpit
          </button>
          <button
            role="tab"
            aria-selected={state.view === 'revisions'}
            className={`nav-tab ${state.view === 'revisions' ? 'active' : ''}`}
            onClick={() => update({ view: 'revisions' })}
          >
            Revision Explorer
          </button>
          <button
            role="tab"
            aria-selected={state.view === 'accuracy'}
            className={`nav-tab ${state.view === 'accuracy' ? 'active' : ''}`}
            onClick={() => update({ view: 'accuracy' })}
          >
            Monthly Accuracy & Risk
          </button>
        </div>

        <div className="nav-meta">
          <ProvenanceBadge provenance={dayData?.provenance} />
        </div>
      </nav>

      <main className="main-content" id="main-content">
        {state.view === 'cockpit' && <DecisionCockpit state={state} update={update} />}
        {state.view === 'revisions' && <RevisionExplorer state={state} update={update} />}
        {state.view === 'accuracy' && <AccuracyAnalysis state={state} update={update} />}
      </main>

      <footer className="desk-footer">
        <div className="footer-left">
          <span>Wind Desk UK · Elexon BMRS WINDFOR & FUELHH Decision Support Workspace</span>
        </div>
        <div className="footer-right">
          <span className="muted">Units: MW · Timestamps: Europe/London · All evaluation strictly point-in-time</span>
        </div>
      </footer>
    </div>
  );
}

export function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <AppContent />
    </QueryClientProvider>
  );
}
export default App;
