"""
Data retrieval endpoints (sleep, readiness, activity).
"""

from datetime import datetime
from typing import Optional, List, Dict

from fastapi import APIRouter, Depends, Query, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import DataPoint, JournalEntry
from ..insights_service import InsightsService
from ..schemas import DataPointResponse

router = APIRouter(prefix="/api", tags=["data"])


class CreateDataPointRequest(BaseModel):
    date: str
    source: str
    type: str
    value: float
    extra_data: Optional[Dict] = None


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


@router.get("/data", response_model=List[DataPointResponse])
async def list_data_points(
    type: Optional[str] = Query(None, description="Filter by type (sleep, activity, readiness, energy, mood)"),
    start_date: Optional[str] = Query(None, description="Start date (YYYY-MM-DD)"),
    end_date: Optional[str] = Query(None, description="End date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """List all data points with optional filters."""
    query = db.query(DataPoint)

    if type:
        query = query.filter(DataPoint.type == type)
    if start_date:
        query = query.filter(DataPoint.date >= start_date)
    if end_date:
        query = query.filter(DataPoint.date <= end_date)

    data = query.order_by(DataPoint.date.desc()).all()

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


@router.post("/data", response_model=DataPointResponse)
async def create_data_point(
    request: CreateDataPointRequest,
    db: Session = Depends(get_db)
):
    """Create a new data point."""
    data_point = DataPoint(
        date=request.date,
        source=request.source,
        type=request.type,
        value=request.value,
        extra_data=request.extra_data,
    )
    db.add(data_point)
    db.commit()
    db.refresh(data_point)

    return DataPointResponse(
        id=data_point.id,
        source=data_point.source,
        type=data_point.type,
        date=data_point.date,
        value=data_point.value,
        metadata=data_point.extra_data or {}
    )


@router.delete("/data/{id}")
async def delete_data_point(
    id: int,
    db: Session = Depends(get_db)
):
    """Delete a data point by ID."""
    data_point = db.query(DataPoint).filter(DataPoint.id == id).first()
    if not data_point:
        raise HTTPException(status_code=404, detail="Data point not found")

    db.delete(data_point)
    db.commit()

    return {"success": True}


@router.get("/data/{date}", response_model=List[DataPointResponse])
async def get_data_by_date(
    date: str,
    db: Session = Depends(get_db)
):
    """Get all data points for a specific date."""
    data = db.query(DataPoint).filter(
        DataPoint.date == date
    ).order_by(DataPoint.type).all()

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
