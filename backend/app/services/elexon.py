"""Async Elexon Insights (BMRS) client with timeouts, bounded retries and backoff."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import date, datetime, timedelta
from typing import Any

import httpx

log = logging.getLogger("winddesk.elexon")

WINDFOR_PATH = "/datasets/WINDFOR/stream"
FUELHH_PATH = "/datasets/FUELHH/stream"


class UpstreamError(Exception):
    """Upstream failure with a safe, user-presentable message."""

    def __init__(self, kind: str, message: str, status: int | None = None) -> None:
        super().__init__(message)
        self.kind = kind  # timeout | rate_limited | http | invalid | network
        self.status = status


def _iso(dt: datetime) -> str:
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


class ElexonClient:
    def __init__(
        self,
        base_url: str,
        timeout_s: float = 20.0,
        max_retries: int = 3,
        transport: httpx.AsyncBaseTransport | None = None,
        sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
        backoff_base_s: float = 0.5,
        max_concurrency: int = 3,
    ) -> None:
        self._base_url = base_url.rstrip("/")
        self._timeout = httpx.Timeout(timeout_s)
        self._max_retries = max_retries
        self._transport = transport
        self._sleep = sleep
        self._backoff = backoff_base_s
        self._sem = asyncio.Semaphore(max_concurrency)

    async def _get_json(self, client: httpx.AsyncClient, path: str, params: dict[str, str]) -> list[dict[str, Any]]:
        attempt = 0
        while True:
            try:
                async with self._sem:
                    resp = await client.get(path, params=params)
            except httpx.TimeoutException as exc:
                err = UpstreamError("timeout", "Elexon API did not respond in time.")
                retry_after: float | None = None
                cause: Exception = exc
            except httpx.TransportError as exc:
                err = UpstreamError("network", "Could not reach the Elexon API.")
                retry_after = None
                cause = exc
            else:
                if resp.status_code == 200:
                    try:
                        payload = resp.json()
                    except ValueError as exc:
                        raise UpstreamError("invalid", "Elexon API returned invalid JSON.") from exc
                    rows = payload.get("data") if isinstance(payload, dict) else payload
                    if not isinstance(rows, list) or not all(isinstance(r, dict) for r in rows):
                        raise UpstreamError("invalid", "Elexon API returned an unexpected payload shape.")
                    return rows
                if resp.status_code == 429:
                    err = UpstreamError("rate_limited", "Elexon API rate limit reached.", 429)
                    try:
                        retry_after = min(float(resp.headers.get("Retry-After", "")), 30.0)
                    except ValueError:
                        retry_after = None
                elif resp.status_code >= 500:
                    err = UpstreamError("http", f"Elexon API error (HTTP {resp.status_code}).", resp.status_code)
                    retry_after = None
                else:
                    raise UpstreamError(
                        "http", f"Elexon API rejected the request (HTTP {resp.status_code}).", resp.status_code
                    )
                cause = err

            if attempt >= self._max_retries:
                log.warning("upstream_failed", extra={"path": path, "kind": err.kind, "attempts": attempt + 1})
                raise err from cause
            delay = retry_after if retry_after is not None else self._backoff * (2**attempt)
            log.info("upstream_retry", extra={"path": path, "kind": err.kind, "delay_s": delay})
            attempt += 1
            await self._sleep(delay)

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url,
            timeout=self._timeout,
            transport=self._transport,
            headers={"Accept": "application/json", "User-Agent": "wind-desk/1.0"},
        )

    async def fetch_windfor(
        self, publish_from: datetime, publish_to: datetime, chunk_days: int = 7
    ) -> list[dict[str, Any]]:
        """All WINDFOR vintages published in ``[publish_from, publish_to]``.

        Queried by publish time (not ``latest``) so every historical vintage is preserved.
        """
        windows: list[tuple[datetime, datetime]] = []
        cur = publish_from
        while cur < publish_to:
            nxt = min(cur + timedelta(days=chunk_days), publish_to)
            windows.append((cur, nxt))
            cur = nxt
        async with self._client() as client:
            chunks = await asyncio.gather(
                *(
                    self._get_json(
                        client,
                        WINDFOR_PATH,
                        {"publishDateTimeFrom": _iso(a), "publishDateTimeTo": _iso(b)},
                    )
                    for a, b in windows
                )
            )
        return [row for chunk in chunks for row in chunk]  # overlaps resolved by normaliser

    async def fetch_fuelhh_wind(self, settlement_from: date, settlement_to: date) -> list[dict[str, Any]]:
        async with self._client() as client:
            return await self._get_json(
                client,
                FUELHH_PATH,
                {
                    "settlementDateFrom": settlement_from.isoformat(),
                    "settlementDateTo": settlement_to.isoformat(),
                    "fuelType": "WIND",
                },
            )
