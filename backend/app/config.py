"""Single source of configuration for Wind Desk.

All decision-timing assumptions live here so that the cutoff can be changed
without touching analytics code.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from datetime import date, time
from pathlib import Path
from zoneinfo import ZoneInfo

LONDON = ZoneInfo("Europe/London")

REPO_ROOT = Path(__file__).resolve().parents[2]


def _env(name: str, default: str) -> str:
    value = os.getenv(name)
    return value if value else default


def _resolve_dir(env_name: str, relative_path: str) -> Path:
    explicit = os.getenv(env_name)
    if explicit:
        return Path(explicit).resolve()
    rel = Path(relative_path)
    # Check REPO_ROOT (anchored to config.py location)
    candidate = (REPO_ROOT / rel).resolve()
    if candidate.exists():
        return candidate
    # Check current working directory
    cwd_candidate = (Path.cwd() / rel).resolve()
    if cwd_candidate.exists():
        return cwd_candidate
    # Check Vercel serverless /var/task root
    task_candidate = (Path("/var/task") / rel).resolve()
    if task_candidate.exists():
        return task_candidate
    return candidate


def parse_hhmm(value: str) -> time:
    """Parse an ``HH:MM`` string into a :class:`datetime.time`.

    Raises ``ValueError`` for malformed input.
    """
    parts = value.strip().split(":")
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        raise ValueError(f"cutoff must be HH:MM, got {value!r}")
    hour, minute = int(parts[0]), int(parts[1])
    if not (0 <= hour <= 23 and 0 <= minute <= 59):
        raise ValueError(f"cutoff out of range: {value!r}")
    return time(hour, minute)


@dataclass(frozen=True)
class Settings:
    # ---- Decision timing (ILLUSTRATIVE default, not a market rule) ----
    #: Local (Europe/London) wall-clock time on the decision date at which
    #: the purchasing decision is assumed to be made.
    default_cutoff: time = field(default_factory=lambda: parse_hhmm(_env("DECISION_CUTOFF_LOCAL", "15:30")))
    #: Number of calendar days between decision date and delivery date.
    lead_days: int = int(_env("DECISION_LEAD_DAYS", "1"))

    # ---- Scope of the assignment ----
    decision_start: date = date(2026, 1, 1)
    decision_end: date = date(2026, 1, 31)

    # ---- Data source ----
    #: ``snapshot`` (packaged, reproducible) or ``live`` (Elexon on demand,
    #: falling back to the snapshot if upstream is unavailable).
    data_source: str = _env("DATA_SOURCE", "snapshot")
    snapshot_dir: Path = field(default_factory=lambda: _resolve_dir("SNAPSHOT_DIR", "data/snapshot"))
    elexon_base_url: str = _env("ELEXON_BASE_URL", "https://data.elexon.co.uk/bmrs/api/v1")
    http_timeout_s: float = float(_env("HTTP_TIMEOUT_S", "20"))
    http_max_retries: int = int(_env("HTTP_MAX_RETRIES", "3"))
    live_cache_ttl_s: int = int(_env("LIVE_CACHE_TTL_S", "900"))

    # ---- Web ----
    static_dir: Path = field(default_factory=lambda: _resolve_dir("STATIC_DIR", "frontend/dist"))
    cors_origins: tuple[str, ...] = tuple(o for o in _env("CORS_ORIGINS", "http://localhost:5173").split(",") if o)
    log_level: str = _env("LOG_LEVEL", "INFO")


def get_settings() -> Settings:
    return Settings()
