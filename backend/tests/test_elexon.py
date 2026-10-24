from __future__ import annotations

import json
from datetime import date

import httpx
import pytest

from app.config import Settings
from app.services.elexon import ElexonClient, UpstreamError
from app.services.repository import DataRepository
from tests.conftest import utc


async def no_sleep(_: float) -> None:
    return None


def client_for(handler, retries: int = 2, sleeps: list[float] | None = None) -> ElexonClient:  # type: ignore[no-untyped-def]
    async def record(s: float) -> None:
        if sleeps is not None:
            sleeps.append(s)

    return ElexonClient(
        "https://example.test/api", max_retries=retries, transport=httpx.MockTransport(handler), sleep=record
    )


async def test_success_stream_and_data_wrapper() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        if "FUELHH" in req.url.path:
            assert req.url.params["fuelType"] == "WIND"
            return httpx.Response(200, json={"data": [{"a": 1}]})
        return httpx.Response(200, json=[{"b": 2}])

    c = client_for(h)
    assert await c.fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 2)) == [{"a": 1}]
    rows = await c.fetch_windfor(utc(2026, 1, 1), utc(2026, 1, 20))
    assert rows == [{"b": 2}] * 3  # three 7-day chunks


async def test_retries_server_error_then_succeeds() -> None:
    calls = {"n": 0}
    sleeps: list[float] = []

    def h(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(503) if calls["n"] < 3 else httpx.Response(200, json=[])

    assert await client_for(h, sleeps=sleeps).fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 1)) == []
    assert calls["n"] == 3
    assert sleeps == [0.5, 1.0]  # exponential backoff


async def test_rate_limit_honours_retry_after_then_fails() -> None:
    sleeps: list[float] = []

    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(429, headers={"Retry-After": "2"})

    with pytest.raises(UpstreamError) as e:
        await client_for(h, retries=1, sleeps=sleeps).fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert e.value.kind == "rate_limited"
    assert sleeps == [2.0]


async def test_timeout() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("slow", request=req)

    with pytest.raises(UpstreamError) as e:
        await client_for(h, retries=1).fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert e.value.kind == "timeout"


async def test_client_error_not_retried() -> None:
    calls = {"n": 0}

    def h(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(400, json={"error": "bad"})

    with pytest.raises(UpstreamError) as e:
        await client_for(h).fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert calls["n"] == 1 and e.value.status == 400


@pytest.mark.parametrize("body", [b"not json", json.dumps({"data": "x"}).encode(), json.dumps([1, 2]).encode()])
async def test_invalid_payloads(body: bytes) -> None:
    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=body)

    with pytest.raises(UpstreamError) as e:
        await client_for(h).fetch_fuelhh_wind(date(2026, 1, 1), date(2026, 1, 1))
    assert e.value.kind == "invalid"


async def test_live_repo_falls_back_to_snapshot_with_warning() -> None:
    def h(req: httpx.Request) -> httpx.Response:
        return httpx.Response(500)

    settings = Settings(data_source="live")
    repo = DataRepository(settings, client_for(h, retries=0))
    ds = await repo.get()
    assert ds.provenance.source == "snapshot"
    assert any("Live Elexon query failed" in w for w in ds.provenance.warnings)


async def test_live_repo_caches_and_coalesces() -> None:
    import asyncio

    calls = {"n": 0}

    def h(req: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return httpx.Response(200, json=[])

    repo = DataRepository(Settings(data_source="live"), client_for(h))
    results = await asyncio.gather(*(repo.get() for _ in range(5)))
    assert all(r is results[0] for r in results)
    assert results[0].provenance.source == "live"
    first = calls["n"]
    await repo.get()
    assert calls["n"] == first  # served from cache
