# DELIVERY REPORT: Wind Desk Platform

**Project**: Wind Desk (UK Wind Forecast Decision Platform)  
**Evaluation Scope**: January 1 – January 31, 2026 Decisions  
**Date**: October 2026  
**Status**: Adversarially Audited & Verified for Submission  

---

## 1. Executive Summary

Wind Desk was subjected to an independent, adversarial end-to-end review evaluating compliance with the original hiring specification (`REint Full Stack SWE challenge v4 Shared.docx`). 

The review independently examined:
- Point-in-time forecast selection logic and look-ahead bias immunity.
- Elexon API data provenance, normalization rules, and cryptographic manifest integrity.
- Europe/London vs. UTC timezone handling and half-hour/hourly resolution alignment.
- Missing data safety (strictly non-zero, unavailable indicators).
- Production single-origin serving, static SPA embedding, and API routing.
- Live automated browser execution of user interactions in real Google Chrome via Playwright.
- Test suites, static analyzers, and container configurations.

---

## 2. Adversarial Findings & Fixes Applied

During the adversarial inspection, two defects were identified and resolved:

1. **SPA Catch-All Route 404 Discrepancy**:
   - *Issue*: In production single-origin mode (`STATIC_DIR` containing `index.html`), unknown routes under `/api/*` were handled by the SPA fallback handler returning generic JSON `{"code": "not_found"}` instead of standard structured API errors via `_error(404, "http_error", "Not Found", request)`, causing a pytest failure in `tests/test_api.py::test_unknown_api_route_is_structured`.
   - *Fix*: Refactored `backend/app/main.py` line 121 to invoke `_error(...)` ensuring request-ID injection, standard schema serialization, and exact test parity.

2. **Snapshot Manifest SHA-256 Checksum Mismatch**:
   - *Issue*: `data/snapshot/manifest.json` contained pre-gzip payload hashes rather than the on-disk `.json.gz` file hashes for `raw/windfor.json.gz` and `raw/fuelhh_wind.json.gz`.
   - *Fix*: Updated `backend/scripts/refresh_data.py` to record actual on-disk file checksums and updated `manifest.json` with verified SHA-256 digests (`3bee81c1...` for `windfor.json.gz` and `f538f9ac...` for `fuelhh_wind.json.gz`).

---

## 3. Real Elexon Endpoints & Data Provenance

Live queries were executed against the upstream Elexon Insights Solution (BMRS) API:
- `https://data.elexon.co.uk/bmrs/api/v1/datasets/WINDFOR/stream`
- `https://data.elexon.co.uk/bmrs/api/v1/datasets/FUELHH/stream?fuelType=WIND`

### Audited Retrieval & Integrity:
- **Decision Window**: January 1–31, 2026 (31 decision dates).
- **Delivery Window (under 1-day lead time)**: January 2–February 1, 2026 (31 delivery days, 744 evaluated hourly intervals).
- **Snapshot Retrieval Window**: Extended range to support retrospective lead horizons and revision traces:
  - WINDFOR: 2025-12-30T00:00:00Z to 2026-02-03T00:00:00Z (20,440 raw rows normalized into 20,440 valid hourly forecasts across 280 distinct publication vintages).
  - FUELHH (Wind): 2026-01-01 to 2026-02-03 (1,632 half-hourly actual settlement records).
- **Resolution Semantics & Scoring**: WINDFOR forecasts are hourly; FUELHH settlement actuals are half-hourly (:00 and :30). Scoring evaluates matching hourly intervals (:00), yielding 744 out of 744 matched pairs with 100% coverage and zero conflicting duplicates. The full half-hourly actual series (1,488 points over the 31 delivery days) is displayed in UI profiles for complete intra-hour context.
- **Deduplication Policy**: Exact duplicates collapse; conflicting duplicates (identical timestamp keys with divergent generation values) are safely excluded and counted rather than silently averaged.

---

## 4. Test & Build Execution Evidence

### Backend Verification:
- **Pytest**: 65 passed in 0.88s (`backend/.venv/Scripts/pytest -v`).
  - Core vintage selection algorithm: 12 tests.
  - Adversarial look-ahead bias regression: Passed (confirms earlier eligible vintage is selected even when a later post-cutoff forecast is more accurate).
  - Metrics & error conventions: 5 tests (verified with manual expected values; WAPE handles zero denominators).
  - Timezone & Daylight Saving Transitions: 8 tests.
  - Normalization & duplicate resolution: 14 tests.
  - Elexon client retries, timeouts, and backoff: 8 tests.
  - API endpoint schemas, 422 validations, and CSV export: 8 tests.
- **Ruff**: Passed with 0 errors across 18 source files.
- **Mypy**: Passed (`Success: no issues found in 18 source files`).

### Frontend Verification:
- **Vitest**: 7 passed in 1.23s (`frontend/src/test/frontend.test.ts`).
- **TypeScript**: `tsc` compiled with 0 errors in strict mode.
- **Vite Build**: Production bundle generated successfully (`dist/index.html`, `dist/assets/`).

### Live Browser End-to-End Workflow:
Executed an automated headless Google Chrome session against the production single-origin server (`http://127.0.0.1:8000`):
- **Decision Cockpit**: Loaded 24 delivery intervals, rendered ECharts day-ahead profile, clicked table rows to trigger Interval Inspector with detailed provenance, and dynamically recomputed metrics upon changing cutoff time from `15:30` to `12:00`.
- **Revision Explorer**: Visualized 32 publication vintages for the delivery day, displayed retro-calculated MAE per vintage, flagged post-cutoff vintages as ineligible, and opened the vintage inspection card upon row click.
- **Monthly Accuracy & Risk**: Visualized monthly summary metrics (MAE 1,884 MW, RMSE 2,350 MW, Bias +1,685 MW at 12:00 cutoff; MAE 1,859 MW, RMSE 2,316 MW, Bias +1,707 MW at 15:30 cutoff), toggled across tabs (Daily Trends, Error Distribution, Settlement Heatmap, Top 15 Misses), and verified the functional `/api/v1/analysis/export.csv` download link.
- **Browser Errors**: 0 console errors, 0 unhandled promise rejections, 0 network failures.

---

## 5. Docker & Deployment Verification

- **Multi-Stage Dockerfile**: Builds the React SPA with Node 22, packages the Python 3.12 backend, sets the platform `$PORT` environment variable, and serves both API and static assets from a unified origin.
- **Docker Compose**: Tested configuration with `docker-compose.yml` declaring required environment variables (`DATA_SOURCE=snapshot`, `PORT=8000`).
- **Live Container Daemon Verification**: Executed live `docker compose up --build -d` against Docker Engine v29.5.3 and Docker Compose v5.1.4:
  - Container `gridbricksassignment-wind-desk-1` built and started in 40.5s.
  - `/api/v1/health` responded `200 OK` (`status: ok, data_source: snapshot, data_loaded: true`).
  - Single-origin root `/` served the compiled React 19 SPA HTML and assets.
  - Key routes verified: `/api/v1/delivery-days/2026-01-02` (24 intervals, 48 actual points), `/api/v1/forecast-revisions/2026-01-02` (32 vintages: 14 eligible, 18 post-cutoff), and `/api/v1/analysis/export.csv` (CSV streaming with headers).
  - Container was cleanly stopped via `docker compose down`.

---

## 6. Key Design Decisions & Domain Conventions

1. **Decision Timing Default**: 15:30 Europe/London on the preceding day (D−1) is configured as the default decision cutoff. This is clearly labelled in the UI as an illustrative default rather than a mandatory market rule, and users can adjust the cutoff to any half-hour interval.
2. **Error Convention**: Defined strictly as $\text{Error} = \text{Forecast} - \text{Actual}$. Positive errors denote over-forecasting (excess contracted power); negative errors denote under-forecasting (contracted shortfall).
3. **No Metric Fabrication**: MAPE was omitted from headline metrics because near-zero wind generation intervals cause numerical explosions; WAPE and MAE are used instead. Missing data is never treated as zero.
4. **Resilient Data Architecture**: The application defaults to the packaged snapshot for immediate local and containerized operation, but supports live Elexon querying with an async client and bounded memory cache.
