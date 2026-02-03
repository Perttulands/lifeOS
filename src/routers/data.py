"""
Data retrieval endpoints (sleep, readiness, activity).
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataPoint, JournalEntry
from ..insights_service import InsightsService
from ..schemas import DataPointResponse

router = APIRouter(prefix="/api", tags=["data"])


@router.get("/data/sleep", response_model=List[DataPointResponse])
async def get_sleep_data(
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get sleep data."""
    query = db.query(DataPoint).filter(DataPoint.type == "sleep")

    if start_date:
        query = query.filter(DataPoint.date >= start_date)
    if end_date:
        query = query.filter(DataPoint.date <= end_date)

    data = query.order_by(DataPoint.date.desc()).limit(limit).all()

    return [
        DataPointResponse(
            id=d.id,
            source=d.source,
            type=d.type,
            date=d.date,
            value=d.value,
            metadata=d.extra_data or {}
        )
        for d in data
    ]


@router.get("/data/readiness", response_model=List[DataPointResponse])
async def get_readiness_data(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get readiness score data."""
    query = db.query(DataPoint).filter(DataPoint.type == "readiness")

    if start_date:
        query = query.filter(DataPoint.date >= start_date)
    if end_date:
        query = query.filter(DataPoint.date <= end_date)

    data = query.order_by(DataPoint.date.desc()).limit(limit).all()

    return [
        DataPointResponse(
            id=d.id,
            source=d.source,
            type=d.type,
            date=d.date,
            value=d.value,
            metadata=d.extra_data or {}
        )
        for d in data
    ]


@router.get("/data/activity", response_model=List[DataPointResponse])
async def get_activity_data(
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    limit: int = Query(30, ge=1, le=365),
    db: Session = Depends(get_db)
):
    """Get activity data."""
    query = db.query(DataPoint).filter(DataPoint.type == "activity")

    if start_date:
        query = query.filter(DataPoint.date >= start_date)
    if end_date:
        query = query.filter(DataPoint.date <= end_date)

    data = query.order_by(DataPoint.date.desc()).limit(limit).all()

    return [
        DataPointResponse(
            id=d.id,
            source=d.source,
            type=d.type,
            date=d.date,
            value=d.value,
            metadata=d.extra_data or {}
        )
        for d in data
    ]


@router.get("/today")
async def get_today_summary(
    db: Session = Depends(get_db)
):
    """
    Get today's summary - all relevant data in one call.

    Convenient endpoint for dashboard.
    """
    today = datetime.now().strftime("%Y-%m-%d")
    service = InsightsService(db)

    # Get today's sleep
    sleep = db.query(DataPoint).filter(
        DataPoint.date == today,
        DataPoint.type == "sleep"
    ).first()

    # Get readiness
    readiness = db.query(DataPoint).filter(
        DataPoint.date == today,
        DataPoint.type == "readiness"
    ).first()

    # Get activity
    activity = db.query(DataPoint).filter(
        DataPoint.date == today,
        DataPoint.type == "activity"
    ).first()

    # Get latest energy log
    energy_log = db.query(JournalEntry).filter(
        JournalEntry.date == today
    ).order_by(JournalEntry.created_at.desc()).first()

    # Get today's brief
    brief = service.get_daily_brief(today)

    return {
        "date": today,
        "sleep": {
            "duration_hours": sleep.value if sleep else None,
            "score": sleep.extra_data.get('score') if sleep and sleep.extra_data else None,
            "deep_sleep_hours": sleep.extra_data.get('deep_sleep_hours') if sleep and sleep.extra_data else None
        } if sleep else None,
        "readiness": {
            "score": readiness.value if readiness else None
        } if readiness else None,
        "activity": {
            "score": activity.value if activity else None
        } if activity else None,
        "energy_log": {
            "level": energy_log.energy if energy_log else None,
            "mood": energy_log.mood if energy_log else None,
            "time": energy_log.time if energy_log else None
        } if energy_log else None,
        "brief": {
            "content": brief.content if brief else None,
            "generated_at": brief.created_at.isoformat() if brief else None
        } if brief else None
    }
