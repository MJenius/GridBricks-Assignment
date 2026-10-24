# Submission Checklist: Wind Desk Platform

## 1. Functional Requirements
- [x] **Point-in-Time Forecast Selection**: Pure algorithm implemented in `backend/app/domain/vintage.py` using binary search (`bisect_right`). Look-ahead bias strictly impossible.
- [x] **Configurable Cutoff**: Default 15:30 Europe/London D−1, fully interactive via UI and query parameters (`cutoff`, `lead_days`).
- [x] **Elexon API Integration**: Real historical streams ingested for FUELHH (WIND, 30-min settlement actuals) and WINDFOR (60-min forecast). Scoring aligned on matching hourly intervals with full 48-point actuals disclosed in UI.
- [x] **Decision Window & Provenance**: January 1–31 decisions map to January 2–February 1 delivery (744 matched hourly intervals). Snapshot retrieval range (Dec 30–Feb 3) clearly distinguished from evaluated delivery dates.
- [x] **Metrics**: MAE, RMSE, Mean Bias, and WAPE computed only over matched pairs. Missing data handled without converting to zero.
- [x] **Workspace A (Decision Cockpit)**: Time-series replay, metric cards, interval table, and interval inspector.
- [x] **Workspace B (Revision Explorer)**: Full publication vintage evolution, cutoff visual markers, and eligibility classification.
- [x] **Workspace C (Accuracy & Risk)**: Monthly trends, error distribution (P05/P50/P95), settlement period heatmap, top 15 misses, and raw CSV download.

## 2. Engineering & Code Quality
- [x] **Backend**: FastAPI with Python 3.12+, typed with Pydantic v2 schemas and ZoneInfo timezone handling.
- [x] **Frontend**: React 19, TypeScript with strict mode, Vite, TanStack Query, and tree-shaken Apache ECharts.
- [x] **Testing**: 65 pytest backend tests + Vitest frontend suite. Adversarial look-ahead bias regression test included.
- [x] **Static Analysis**: Ruff format/linting clean; Mypy strict type checking clean.
- [x] **Docker**: Multi-stage `Dockerfile` (Node 22 build + Python 3.12-slim runtime) and `docker-compose.yml`. Single-origin static SPA serving from FastAPI.
- [x] **CI**: GitHub Actions workflow (`.github/workflows/ci.yml`) covering linting, type-checking, and tests.

## 3. Submission Artifacts
- [x] **README.md**: Architecture diagrams, setup guide, API endpoints, mathematical definitions, assumptions, and AI disclosure.
- [x] **docs/VIDEO_SCRIPT.md**: 2-part presentation script under 10 minutes (Customer Presentation + Technical Review).
- [x] **DELIVERY_REPORT.md**: Final delivery status, test execution results, and operational details.
