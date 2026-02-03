"""
Oura integration endpoints.
"""

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..config import settings
from ..database import get_db
from ..integrations.oura import OuraSyncService, sync_oura_data
from ..schemas import (
    OuraSyncRequest,
    OuraSyncResponse,
    OuraSyncResultResponse,
)

router = APIRouter(prefix="/api/oura", tags=["oura"])


@router.post("/sync", response_model=OuraSyncResponse)
async def sync_oura(
    request: OuraSyncRequest,
    db: Session = Depends(get_db)
):
    """
    Sync Oura data for a date range.

    If no dates provided, syncs today's data.
    Fetches sleep, activity, and readiness data.
    """
    results = sync_oura_data(
        db=db,
        start_date=request.start_date,
        end_date=request.end_date
    )

    total = sum(r.records_synced for r in results)

    return OuraSyncResponse(
        results=[
            OuraSyncResultResponse(
                success=r.success,
                data_type=r.data_type.value,
                records_synced=r.records_synced,
                date_range=list(r.date_range),
                errors=r.errors
            )
            for r in results
        ],
        total_synced=total
    )


@router.post("/backfill", response_model=OuraSyncResponse)
async def backfill_oura(
    days: int = 30,
    db: Session = Depends(get_db)
):
    """
    Backfill historical Oura data.

    Fetches the last N days of sleep, activity, and readiness data.
    Use on first setup to populate historical data.
    """
    service = OuraSyncService(db)
    results = service.backfill(days=days)

    total = sum(r.records_synced for r in results)

    return OuraSyncResponse(
        results=[
            OuraSyncResultResponse(
                success=r.success,
                data_type=r.data_type.value,
                records_synced=r.records_synced,
                date_range=list(r.date_range),
                errors=r.errors
            )
            for r in results
        ],
        total_synced=total
    )


@router.get("/status")
async def oura_status():
    """
    Check Oura integration status.

    Returns whether the Oura token is configured.
    """
    has_token = bool(settings.oura_token)

    return {
        "configured": has_token,
        "base_url": settings.oura_base_url
    }
