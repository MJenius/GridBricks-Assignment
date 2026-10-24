"""Root-level entrypoint for Vercel deployment of the Wind Desk FastAPI application.

Exposes the `app` instance expected by Vercel's zero-config FastAPI detector
and fluid compute runtime.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

# Ensure the backend directory and root directory are on sys.path
_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"

if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import uvicorn  # noqa: E402
from app.main import app, create_app  # noqa: E402

__all__ = ["app", "create_app"]


if __name__ == "__main__":
    port = int(os.getenv("PORT", "8000"))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
