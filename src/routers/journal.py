"""
Mood/Energy Journal endpoints.

Phase 2 feature: Rich journaling with 1-10 scale, mood tracking,
and AI-powered insights.
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import APIRouter, Depends, Query, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func, desc

from ..database import get_db
from ..models import JournalEntry, DataPoint


router = APIRouter(prefix="/api/journal", tags=["journal"])


# === Schemas ===

from pydantic import BaseModel, Field


class JournalLogRequest(BaseModel):
    """Request to log mood/energy."""
    energy: int = Field(..., ge=1, le=10, description="Energy level 1-10")
    mood: Optional[int] = Field(None, ge=1, le=10, description="Mood level 1-10")
    notes: Optional[str] = Field(None, max_length=2000, description="Optional notes")
    tags: Optional[List[str]] = Field(default_factory=list, description="Optional tags")


class JournalEntryResponse(BaseModel):
    """Response for a journal entry."""
    id: int
    date: str
    time: Optional[str]
    energy: Optional[int]
    mood: Optional[int]
    notes: Optional[str]
    tags: List[str]
    created_at: str

    class Config:
        from_attributes = True


class JournalStatsResponse(BaseModel):
    """Stats for journal entries over a period."""
    period_days: int
    total_entries: int
    avg_energy: Optional[float]
    avg_mood: Optional[float]
    energy_trend: str  # "up", "down", "stable"
    mood_trend: str
    most_common_tags: List[str]
    entries_by_day: dict  # date -> count


class JournalTrendPoint(BaseModel):
    """Single point in a trend."""
    date: str
    energy: Optional[float]
    mood: Optional[float]
    entry_count: int


# === Endpoints ===

@router.post("/log", response_model=JournalEntryResponse)
async def log_journal_entry(
    request: JournalLogRequest,
    db: Session = Depends(get_db)
):
    """
    Log a mood/energy journal entry.

    Uses 1-10 scale for both energy and mood.
    Optionally add notes and tags.
    """
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")

    # Create journal entry
    entry = JournalEntry(
        date=date,
        time=time,
        energy=request.energy,
        mood=request.mood,
        notes=request.notes,
        tags=request.tags or []
    )
    db.add(entry)

    # Also create data points for pattern analysis
    # Energy data point
    energy_dp = DataPoint(
        source="journal",
        type="energy",
        date=date,
        value=request.energy,
        extra_data={
            "time": time,
            "scale": "1-10",
            "journal_id": None  # Will update after commit
        }
    )
    db.add(energy_dp)

    # Mood data point (if provided)
    if request.mood is not None:
        mood_dp = DataPoint(
            source="journal",
            type="mood",
            date=date,
            value=request.mood,
            extra_data={
                "time": time,
                "scale": "1-10",
                "journal_id": None
            }
        )
        db.add(mood_dp)

    db.commit()
    db.refresh(entry)

    # Update data point references
    energy_dp.extra_data["journal_id"] = entry.id
    if request.mood is not None:
        mood_dp.extra_data["journal_id"] = entry.id
    db.commit()

    return JournalEntryResponse(
        id=entry.id,
        date=entry.date,
        time=entry.time,
        energy=entry.energy,
        mood=entry.mood,
        notes=entry.notes,
        tags=entry.tags or [],
        created_at=entry.created_at.isoformat()
    )


@router.get("/entries", response_model=List[JournalEntryResponse])
async def get_journal_entries(
    days: int = Query(7, ge=1, le=90, description="Number of days to fetch"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """
    Get journal entries for the last N days.
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date >= start_date)
        .order_by(desc(JournalEntry.created_at))
        .limit(limit)
        .all()
    )

    return [
        JournalEntryResponse(
            id=e.id,
            date=e.date,
            time=e.time,
            energy=e.energy,
            mood=e.mood,
            notes=e.notes,
            tags=e.tags or [],
            created_at=e.created_at.isoformat()
        )
        for e in entries
    ]


@router.get("/today", response_model=List[JournalEntryResponse])
async def get_today_entries(db: Session = Depends(get_db)):
    """
    Get all journal entries for today.
    """
    today = datetime.now().strftime("%Y-%m-%d")

    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date == today)
        .order_by(desc(JournalEntry.created_at))
        .all()
    )

    return [
        JournalEntryResponse(
            id=e.id,
            date=e.date,
            time=e.time,
            energy=e.energy,
            mood=e.mood,
            notes=e.notes,
            tags=e.tags or [],
            created_at=e.created_at.isoformat()
        )
        for e in entries
    ]


@router.get("/stats", response_model=JournalStatsResponse)
async def get_journal_stats(
    days: int = Query(7, ge=1, le=90, description="Number of days for stats"),
    db: Session = Depends(get_db)
):
    """
    Get statistics for journal entries over a period.
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date >= start_date)
        .all()
    )

    if not entries:
        return JournalStatsResponse(
            period_days=days,
            total_entries=0,
            avg_energy=None,
            avg_mood=None,
            energy_trend="stable",
            mood_trend="stable",
            most_common_tags=[],
            entries_by_day={}
        )

    # Calculate averages
    energies = [e.energy for e in entries if e.energy is not None]
    moods = [e.mood for e in entries if e.mood is not None]

    avg_energy = sum(energies) / len(energies) if energies else None
    avg_mood = sum(moods) / len(moods) if moods else None

    # Calculate trends (compare first half to second half)
    def calc_trend(values):
        if len(values) < 2:
            return "stable"
        mid = len(values) // 2
        first_half_avg = sum(values[:mid]) / mid if mid > 0 else 0
        second_half_avg = sum(values[mid:]) / (len(values) - mid) if len(values) - mid > 0 else 0
        diff = second_half_avg - first_half_avg
        if diff > 0.5:
            return "up"
        elif diff < -0.5:
            return "down"
        return "stable"

    # Collect all tags
    all_tags = []
    for e in entries:
        if e.tags:
            all_tags.extend(e.tags)

    # Count tag frequency
    tag_counts = {}
    for tag in all_tags:
        tag_counts[tag] = tag_counts.get(tag, 0) + 1
    most_common = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:5]

    # Entries by day
    entries_by_day = {}
    for e in entries:
        entries_by_day[e.date] = entries_by_day.get(e.date, 0) + 1

    return JournalStatsResponse(
        period_days=days,
        total_entries=len(entries),
        avg_energy=round(avg_energy, 1) if avg_energy else None,
        avg_mood=round(avg_mood, 1) if avg_mood else None,
        energy_trend=calc_trend(energies),
        mood_trend=calc_trend(moods),
        most_common_tags=[t[0] for t in most_common],
        entries_by_day=entries_by_day
    )


@router.get("/trends", response_model=List[JournalTrendPoint])
async def get_journal_trends(
    days: int = Query(7, ge=1, le=90, description="Number of days"),
    db: Session = Depends(get_db)
):
    """
    Get daily averages for trends visualization.
    """
    start_date = (datetime.now() - timedelta(days=days)).strftime("%Y-%m-%d")

    # Get all entries in the period
    entries = (
        db.query(JournalEntry)
        .filter(JournalEntry.date >= start_date)
        .all()
    )

    # Group by date
    by_date = {}
    for e in entries:
        if e.date not in by_date:
            by_date[e.date] = {"energies": [], "moods": [], "count": 0}
        if e.energy is not None:
            by_date[e.date]["energies"].append(e.energy)
        if e.mood is not None:
            by_date[e.date]["moods"].append(e.mood)
        by_date[e.date]["count"] += 1

    # Generate all dates in range
    result = []
    current = datetime.now() - timedelta(days=days - 1)
    for _ in range(days):
        date_str = current.strftime("%Y-%m-%d")
        data = by_date.get(date_str, {"energies": [], "moods": [], "count": 0})

        result.append(JournalTrendPoint(
            date=date_str,
            energy=round(sum(data["energies"]) / len(data["energies"]), 1) if data["energies"] else None,
            mood=round(sum(data["moods"]) / len(data["moods"]), 1) if data["moods"] else None,
            entry_count=data["count"]
        ))
        current += timedelta(days=1)

    return result


@router.delete("/{entry_id}")
async def delete_journal_entry(
    entry_id: int,
    db: Session = Depends(get_db)
):
    """
    Delete a journal entry.
    """
    entry = db.query(JournalEntry).filter(JournalEntry.id == entry_id).first()

    if not entry:
        raise HTTPException(status_code=404, detail="Entry not found")

    db.delete(entry)
    db.commit()

    return {"success": True, "message": "Entry deleted"}
