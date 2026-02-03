"""
Historical data backfill endpoints.

Provides endpoints for importing historical data from Oura and Calendar
with progress tracking.
"""
from typing import Optional, Dict, Any

from fastapi import APIRouter, Depends, HTTPException, Query, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..backfill import (
    BackfillManager,
    BackfillSource,
    BackfillStatus,
    OuraBackfillService,
    CalendarBackfillService,
    get_current_progress,
    clear_progress,
)

router = APIRouter(prefix="/api/backfill", tags=["backfill"])


# === Pydantic Models ===

class BackfillProgressResponse(BaseModel):
    source: str
    status: str
    total_days: int
    completed_days: int
    records_synced: int
    percent_complete: float
    current_date: Optional[str] = None
    started_at: Optional[str] = None
    completed_at: Optional[str] = None
    elapsed_seconds: float
    errors: list[str]


class BackfillResultResponse(BaseModel):
    oura: Optional[BackfillProgressResponse] = None
    calendar: Optional[BackfillProgressResponse] = None
    total_records: int
    all_completed: bool


class DataSummaryResponse(BaseModel):
    oura: Dict[str, Any]
    calendar: Dict[str, Any]


class BackfillRequest(BaseModel):
    oura_days: int = 90
    calendar_days_back: int = 90
    calendar_days_forward: int = 30
    sources: Optional[list[str]] = None  # ["oura", "calendar"] or None for all


# === Endpoints ===

@router.get("/status")
async def get_backfill_status(db: Session = Depends(get_db)):
    """
    Get data summary and backfill status.

    Returns current data counts and whether backfill is needed for each source.
    """
    manager = BackfillManager(db)
    summary = manager.get_data_summary()

    # Also check for any in-progress backfills
    oura_progress = get_current_progress(BackfillSource.OURA)
    calendar_progress = get_current_progress(BackfillSource.CALENDAR)

    return {
        "data_summary": summary,
        "in_progress": {
            "oura": oura_progress.to_dict() if oura_progress and oura_progress.status == BackfillStatus.IN_PROGRESS else None,
            "calendar": calendar_progress.to_dict() if calendar_progress and calendar_progress.status == BackfillStatus.IN_PROGRESS else None
        }
    }


@router.get("/progress/{source}")
async def get_progress(source: str):
    """
    Get progress for a specific backfill operation.

    Args:
        source: "oura" or "calendar"

    Returns progress details or 404 if no backfill in progress.
    """
    try:
        backfill_source = BackfillSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    progress = get_current_progress(backfill_source)

    if not progress:
        return {
            "source": source,
            "status": "none",
            "message": "No backfill in progress or recently completed"
        }

    return progress.to_dict()


@router.post("/oura", response_model=BackfillProgressResponse)
async def backfill_oura(
    days: int = Query(90, ge=7, le=365, description="Days of history to import"),
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db)
):
    """
    Start Oura data backfill.

    Imports the specified number of days of sleep, activity, and readiness data.
    For large backfills (>30 days), consider running in background.

    Args:
        days: Number of days to import (7-365, default 90)

    Returns progress immediately. Poll /progress/oura for updates during long imports.
    """
    # Check if backfill already in progress
    existing = get_current_progress(BackfillSource.OURA)
    if existing and existing.status == BackfillStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=409,
            detail="Oura backfill already in progress"
        )

    # Clear any previous progress
    clear_progress(BackfillSource.OURA)

    service = OuraBackfillService(db)
    progress = service.backfill(days=days)

    return BackfillProgressResponse(
        source=progress.source.value,
        status=progress.status.value,
        total_days=progress.total_days,
        completed_days=progress.completed_days,
        records_synced=progress.records_synced,
        percent_complete=progress.percent_complete,
        current_date=progress.current_date,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
        elapsed_seconds=progress.elapsed_seconds,
        errors=progress.errors
    )


@router.post("/calendar", response_model=BackfillProgressResponse)
async def backfill_calendar(
    days_back: int = Query(90, ge=7, le=365, description="Days of history to import"),
    days_forward: int = Query(30, ge=0, le=90, description="Days of future events"),
    db: Session = Depends(get_db)
):
    """
    Start Google Calendar backfill.

    Imports calendar events for the specified period.
    Requires Google Calendar to be connected first.

    Args:
        days_back: Days of history (7-365, default 90)
        days_forward: Days of future events (0-90, default 30)
    """
    # Check if backfill already in progress
    existing = get_current_progress(BackfillSource.CALENDAR)
    if existing and existing.status == BackfillStatus.IN_PROGRESS:
        raise HTTPException(
            status_code=409,
            detail="Calendar backfill already in progress"
        )

    # Clear any previous progress
    clear_progress(BackfillSource.CALENDAR)

    service = CalendarBackfillService(db)
    progress = service.backfill(days_back=days_back, days_forward=days_forward)

    return BackfillProgressResponse(
        source=progress.source.value,
        status=progress.status.value,
        total_days=progress.total_days,
        completed_days=progress.completed_days,
        records_synced=progress.records_synced,
        percent_complete=progress.percent_complete,
        current_date=progress.current_date,
        started_at=progress.started_at.isoformat() if progress.started_at else None,
        completed_at=progress.completed_at.isoformat() if progress.completed_at else None,
        elapsed_seconds=progress.elapsed_seconds,
        errors=progress.errors
    )


@router.post("/all", response_model=BackfillResultResponse)
async def backfill_all(
    request: BackfillRequest,
    db: Session = Depends(get_db)
):
    """
    Run backfill for all configured sources.

    Imports historical data from Oura and Calendar based on configuration.
    Only backfills sources that are properly configured.

    Args:
        oura_days: Days of Oura history (default 90)
        calendar_days_back: Days of calendar history (default 90)
        calendar_days_forward: Days of future calendar events (default 30)
        sources: Optional list of sources to backfill (["oura", "calendar"])
    """
    manager = BackfillManager(db)

    # Determine which sources to backfill
    sources = request.sources or ["oura", "calendar"]

    result = manager.run_full_backfill(
        oura_days=request.oura_days if "oura" in sources else 0,
        calendar_days_back=request.calendar_days_back if "calendar" in sources else 0,
        calendar_days_forward=request.calendar_days_forward if "calendar" in sources else 0
    )

    return BackfillResultResponse(
        oura=BackfillProgressResponse(
            source=result.oura.source.value,
            status=result.oura.status.value,
            total_days=result.oura.total_days,
            completed_days=result.oura.completed_days,
            records_synced=result.oura.records_synced,
            percent_complete=result.oura.percent_complete,
            current_date=result.oura.current_date,
            started_at=result.oura.started_at.isoformat() if result.oura.started_at else None,
            completed_at=result.oura.completed_at.isoformat() if result.oura.completed_at else None,
            elapsed_seconds=result.oura.elapsed_seconds,
            errors=result.oura.errors
        ) if result.oura else None,
        calendar=BackfillProgressResponse(
            source=result.calendar.source.value,
            status=result.calendar.status.value,
            total_days=result.calendar.total_days,
            completed_days=result.calendar.completed_days,
            records_synced=result.calendar.records_synced,
            percent_complete=result.calendar.percent_complete,
            current_date=result.calendar.current_date,
            started_at=result.calendar.started_at.isoformat() if result.calendar.started_at else None,
            completed_at=result.calendar.completed_at.isoformat() if result.calendar.completed_at else None,
            elapsed_seconds=result.calendar.elapsed_seconds,
            errors=result.calendar.errors
        ) if result.calendar else None,
        total_records=result.total_records,
        all_completed=result.all_completed
    )


@router.delete("/progress/{source}")
async def clear_backfill_progress(source: str):
    """
    Clear progress tracking for a source.

    Use this to reset progress after a failed backfill.
    """
    try:
        backfill_source = BackfillSource(source)
    except ValueError:
        raise HTTPException(status_code=400, detail=f"Invalid source: {source}")

    clear_progress(backfill_source)

    return {"success": True, "message": f"Progress cleared for {source}"}
