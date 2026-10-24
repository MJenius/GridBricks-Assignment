"""Root-level index entrypoint alias exposing the FastAPI application for Vercel."""

from __future__ import annotations

from main import app, create_app

__all__ = ["app", "create_app"]
