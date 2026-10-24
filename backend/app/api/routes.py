"""HTTP routes for /api/v1."""

from __future__ import annotations

from datetime import date, time, timedelta
from typing import Annotated

from fastapi import APIRouter, Depends, Query, Request
from fastapi.responses import Response

from app import __version__
from app.config import Settings, parse_hhmm
from app.schemas.api import AnalysisOut, DeliveryDayOut, ErrorResponse, HealthOut, RevisionsOut
from app.services import reporting
from app.services.repository import MAX_LEAD_DAYS, DataRepository, Dataset

router = APIRouter(prefix="/api/v1")

ERRORS: dict[int | str, dict[str, object]] = {
    422: {"model": ErrorResponse, "description": "Invalid parameters"},
    503: {"model": ErrorResponse, "description": "Data unavailable"},
}


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status, self.code, self.message = status, code, message


def get_settings_dep(request: Request) -> Settings:
    settings: Settings = request.app.state.settings
    return settings


def get_repo(request: Request) -> DataRepository:
    repo: DataRepository = request.app.state.repo
    return repo


async def get_dataset(repo: Annotated[DataRepository, Depends(get_repo)]) -> Dataset:
    try:
        return await repo.get()
    except (OSError, ValueError, KeyError) as exc:
        raise ApiError(503, "data_unavailable", "Historical data could not be loaded.") from exc


SettingsDep = Annotated[Settings, Depends(get_settings_dep)]
DatasetDep = Annotated[Dataset, Depends(get_dataset)]
CutoffQ = Annotated[
    str | None, Query(description="Decision cutoff HH:MM, Europe/London, on the decision date", examples=["15:30"])
]
LeadQ = Annotated[int | None, Query(ge=1, le=MAX_LEAD_DAYS, description="Days between decision date and delivery date")]


def resolve_timing(settings: Settings, cutoff: str | None, lead_days: int | None) -> tuple[time, int]:
    try:
        cut = parse_hhmm(cutoff) if cutoff is not None else settings.default_cutoff
    except ValueError as exc:
        raise ApiError(422, "invalid_cutoff", str(exc)) from exc
    return cut, lead_days if lead_days is not None else settings.lead_days


def check_decision(settings: Settings, d: date, label: str) -> None:
    if not settings.decision_start <= d <= settings.decision_end:
        raise ApiError(
            422,
            "out_of_scope",
            f"{label} {d.isoformat()} is outside the decision period "
            f"{settings.decision_start.isoformat()}..{settings.decision_end.isoformat()}.",
        )


@router.get("/health", response_model=HealthOut)
async def health(
    request: Request, settings: SettingsDep, repo: Annotated[DataRepository, Depends(get_repo)]
) -> HealthOut:
    try:
        ds = repo.snapshot()
        return HealthOut(
            status="ok",
            version=__version__,
            data_source=settings.data_source,
            data_loaded=True,
            retrieved_at=ds.provenance.retrieved_at,
        )
    except (OSError, ValueError, KeyError):
        return HealthOut(
            status="degraded",
            version=__version__,
            data_source=settings.data_source,
            data_loaded=False,
            retrieved_at=None,
            detail="Snapshot could not be loaded.",
        )


@router.get("/analysis", response_model=AnalysisOut, responses=ERRORS)
async def get_analysis(
    settings: SettingsDep,
    ds: DatasetDep,
    decision_from: date = date(2026, 1, 1),
    decision_to: date = date(2026, 1, 31),
    cutoff: CutoffQ = None,
    lead_days: LeadQ = None,
) -> AnalysisOut:
    """Accuracy of decision-time forecasts across a range of decision dates."""
    cut, lead = resolve_timing(settings, cutoff, lead_days)
    check_decision(settings, decision_from, "decision_from")
    check_decision(settings, decision_to, "decision_to")
    if decision_to < decision_from:
        raise ApiError(422, "invalid_range", "decision_to must be on or after decision_from.")
    return reporting.analysis(ds, settings, decision_from, decision_to, cut, lead)


@router.get("/analysis/export.csv", responses={**ERRORS, 200: {"content": {"text/csv": {}}}})
async def export_analysis(
    settings: SettingsDep,
    ds: DatasetDep,
    decision_from: date = date(2026, 1, 1),
    decision_to: date = date(2026, 1, 31),
    cutoff: CutoffQ = None,
    lead_days: LeadQ = None,
) -> Response:
    """Interval-level observations and calculated errors as CSV."""
    cut, lead = resolve_timing(settings, cutoff, lead_days)
    check_decision(settings, decision_from, "decision_from")
    check_decision(settings, decision_to, "decision_to")
    if decision_to < decision_from:
        raise ApiError(422, "invalid_range", "decision_to must be on or after decision_from.")
    body = reporting.export_csv(ds, decision_from, decision_to, cut, lead)
    name = f"wind-desk_{decision_from}_{decision_to}_cutoff{cut.strftime('%H%M')}_lead{lead}.csv"
    return Response(
        body, media_type="text/csv; charset=utf-8", headers={"Content-Disposition": f'attachment; filename="{name}"'}
    )


@router.get("/delivery-days/{delivery_date}", response_model=DeliveryDayOut, responses=ERRORS)
async def get_delivery_day(
    delivery_date: date, settings: SettingsDep, ds: DatasetDep, cutoff: CutoffQ = None, lead_days: LeadQ = None
) -> DeliveryDayOut:
    """Decision replay for one delivery day (eligible forecast vs actual)."""
    cut, lead = resolve_timing(settings, cutoff, lead_days)
    check_decision(settings, delivery_date - timedelta(days=lead), "Decision date for this delivery date")
    return reporting.delivery_day(ds, settings, delivery_date, cut, lead)


@router.get("/forecast-revisions/{delivery_date}", response_model=RevisionsOut, responses=ERRORS)
async def get_revisions(
    delivery_date: date, settings: SettingsDep, ds: DatasetDep, cutoff: CutoffQ = None, lead_days: LeadQ = None
) -> RevisionsOut:
    """All WINDFOR vintages covering a delivery day, flagged by cutoff eligibility."""
    cut, lead = resolve_timing(settings, cutoff, lead_days)
    check_decision(settings, delivery_date - timedelta(days=lead), "Decision date for this delivery date")
    return reporting.revisions(ds, settings, delivery_date, cut, lead)
