# Video Presentation Script: Wind Desk

**Total Duration: 9:30 min (Max 10:00 min)**

---

## Part 1: Customer Presentation (Energy Utility Procurement Team)
*Target: ~4:30 minutes*

### [0:00 - 1:00] The Procurement Problem & Product Introduction
"Hello everyone. Today I'm pleased to present **Wind Desk**, the decision-support platform designed specifically for your day-ahead power procurement team.

As a UK utility balancing volatile customer load, every day before gate closure you face a critical question: *How much thermal or market power do we need to procure to balance our position after expected wind generation?*

Day-ahead decisions must be committed one day ahead—say by 15:30. But wind forecasts are constantly being revised. When evaluating performance after the fact, standard dashboards often show the *latest* forecast published right before delivery. That creates dangerous look-ahead bias. You need to know: **What forecast was actually on our screens when we signed the contract, and how accurate was it?** That's exactly what Wind Desk answers."

### [1:00 - 2:30] Decision Cockpit Walkthrough
*(Screen showing Decision Cockpit at `http://localhost:8000`)*

"Here is the **Decision Cockpit**.
- On January 1st, 2026, we made our purchasing commitment for January 2nd delivery.
- The cutoff is clearly configured to 15:30 Europe/London.
- Notice the metric strip: On this day, national wind actual generation averaged around 10,000 to 14,000 MW. Our day-ahead MAE was 3,415 MW with a strong positive bias of +3,415 MW.
- Looking at the profile replay chart: The solid amber line represents the exact WINDFOR forecast published at 15:30 on Jan 1st. The green line shows actual delivery from FUELHH.
- Because wind was substantially over-forecast across midday, the procurement desk contracted power expecting high wind, leaving an excess position that had to be sold down in the balancing mechanism."

### [2:30 - 3:30] Interval Inspection & Provenance
*(Clicking an interval on the chart, e.g. 12:00)*

"Notice what happens when I select interval 12:00:
- Our inspector displays the exact publication timestamp (`2026-01-01 15:30 UTC`), the 20.5-hour lead horizon, the actual wind of 10,240 MW, and the forecast of 14,500 MW.
- In the top right, our **Provenance Badge** shows that every single observation comes from certified Elexon BMRS streams, complete with data quality verification counts showing zero conflicting duplicates."

### [3:30 - 4:30] Revision Explorer & Procurement Risk
*(Navigating to Revision Explorer)*

"Now let's switch to the **Forecast Revision Explorer**.
- Here, we see every single forecast vintage published for this delivery day.
- Crucially, notice the purple dashed lines: these are vintages published *after* 15:30 on the decision day. As delivery approached, the forecast adjusted down toward reality.
- But Wind Desk strictly isolates post-cutoff revisions from decision scoring. This proves whether forecasting error was driven by physical meteorological difficulty or if an earlier market cutoff would have altered the procurement outcome.
- This objective audit gives your trading analysts the empirical evidence needed to negotiate imbalance reserves."

---

## Transition (0:15)
*"Now, let's switch hats and dive into Part 2: the technical architecture and engineering review for our technical lead."*

---

## Part 2: Technical Review (Internal Tech Lead)
*Target: ~4:45 minutes*

### [4:45 - 6:00] Architecture & Domain Boundaries
*(Showing Mermaid Architecture Diagram in README)*

"Welcome. Wind Desk is built with a strict separation of concerns across a clean stack:
- **Backend**: Python 3.12 with FastAPI and Pydantic v2.
- **Frontend**: React 19, TypeScript with strict mode, and tree-shaken Apache ECharts.
- **Data Architecture**:
  - We do not query the Elexon API from the browser. The Python backend handles retrieval using an asynchronous `httpx` client with exponential backoff and bounded concurrency.
  - The repository features a bounded TTL cache and ships with a self-contained, reproducible 20,440-row snapshot covering the complete January 2026 decision window."

### [6:00 - 7:15] Point-in-Time Vintage Selection & Deduplication
*(Showing `backend/app/domain/vintage.py` and `backend/app/services/normalize.py`)*

"Let's look at the core mathematical invariant in `vintage.py`.
- For any delivery interval $t$ and cutoff $c$:
  `selected_forecast(t, c) = max(v for v in vintages[t] if v.publish_time <= c)`
- We index target delivery hours and use bisection search (`bisect_right`) over pre-sorted publication times.
- If no eligible forecast exists prior to the cutoff, it returns `None`. We never substitute the latest forecast.
- In `normalize.py`, our duplicate resolution policy is deterministic: exact duplicates collapse, while conflicting duplicates for the same $(t, \text{publishTime})$ are flagged and excluded rather than silently averaged."

### [7:15 - 8:15] Testing Rigor & Adversarial Regression
*(Showing test runner output: 65 passing backend tests + Vitest tests)*

"Testing was treated as a first-class requirement:
- Our test suite in `backend/tests/` has 65 automated tests.
- Crucially, `test_look_ahead_bias_regression()` tests an adversarial scenario: an afternoon forecast revision published after the cutoff perfectly predicts the actual generation. The test asserts that the scoring algorithm strictly uses the earlier, less accurate vintage available at cutoff time, proving that look-ahead bias is physically impossible.
- Our frontend uses Vitest and React Testing Library to test date clamping, metric formatting, and URL state synchronization."

### [8:15 - 9:30] Docker, CI & Production Deployment
*(Showing `Dockerfile` and `.github/workflows/ci.yml`)*

"Finally, operations and deployment:
- **Docker**: We provide a multi-stage `Dockerfile`. Stage 1 builds the Vite React application; Stage 2 bundles the lightweight `python:3.12-slim` runner. FastAPI serves both the REST endpoints and the static SPA under a unified origin, eliminating CORS complexity.
- **CI**: Our GitHub Actions pipeline enforces Ruff linting, Mypy strict type checking, pytest, and Vitest on every commit.
- In summary, Wind Desk delivers a mathematically sound, auditable, and production-ready intelligence platform."
