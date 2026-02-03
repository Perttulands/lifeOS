"""
Insights and AI-generated content endpoints.
"""

from datetime import datetime
from typing import Optional, List

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Insight
from ..insights_service import InsightsService
from ..schemas import (
    InsightResponse,
    PatternResponse,
    EnergyPrediction,
    GenerateRequest,
)

router = APIRouter(prefix="/api", tags=["insights"])


@router.get("/insights/brief", response_model=Optional[InsightResponse])
async def get_daily_brief(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD), defaults to today"),
    generate: bool = Query(False, description="Generate if not exists"),
    db: Session = Depends(get_db)
):
    """
    Get the daily brief for a date.

    If generate=true and no brief exists, one will be generated.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    service = InsightsService(db)

    if generate:
        insight = service.generate_daily_brief(date)
    else:
        insight = service.get_daily_brief(date)

    if not insight:
        return None

    return InsightResponse(
        id=insight.id,
        type=insight.type,
        date=insight.date,
        content=insight.content,
        confidence=insight.confidence,
        created_at=insight.created_at.isoformat()
    )


@router.get("/insights/patterns", response_model=List[PatternResponse])
async def get_patterns(
    active_only: bool = Query(True, description="Only return active patterns"),
    db: Session = Depends(get_db)
):
    """Get detected patterns from historical data."""
    service = InsightsService(db)
    patterns = service.get_patterns(active_only=active_only)

    return [
        PatternResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            pattern_type=p.pattern_type,
            variables=p.variables or [],
            strength=p.strength or 0,
            confidence=p.confidence or 0,
            sample_size=p.sample_size or 0,
            actionable=p.actionable
        )
        for p in patterns
    ]


@router.post("/insights/detect-patterns", response_model=List[PatternResponse])
async def detect_patterns(
    days: int = Query(30, ge=7, le=90, description="Days of history to analyze"),
    force: bool = Query(False, description="Force re-detection"),
    db: Session = Depends(get_db)
):
    """
    Run pattern detection on historical data.

    Analyzes the last N days and stores detected patterns.
    """
    service = InsightsService(db)
    patterns = service.detect_patterns(days=days, force=force)

    return [
        PatternResponse(
            id=p.id,
            name=p.name,
            description=p.description,
            pattern_type=p.pattern_type,
            variables=p.variables or [],
            strength=p.strength or 0,
            confidence=p.confidence or 0,
            sample_size=p.sample_size or 0,
            actionable=p.actionable
        )
        for p in patterns
    ]


@router.post("/insights/generate", response_model=InsightResponse)
async def generate_insight(
    request: GenerateRequest,
    db: Session = Depends(get_db)
):
    """
    Force generate/regenerate an insight.

    Types: daily_brief, weekly_review, energy_prediction
    """
    service = InsightsService(db)

    try:
        insight = service.force_regenerate(
            insight_type=request.insight_type,
            date=request.date
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    if not insight:
        raise HTTPException(status_code=500, detail="Failed to generate insight")

    return InsightResponse(
        id=insight.id,
        type=insight.type,
        date=insight.date,
        content=insight.content,
        confidence=insight.confidence,
        created_at=insight.created_at.isoformat()
    )


@router.get("/predictions/energy", response_model=EnergyPrediction)
async def get_energy_prediction(
    date: Optional[str] = Query(None, description="Date (YYYY-MM-DD)"),
    db: Session = Depends(get_db)
):
    """
    Get energy prediction for a date.

    Predicts overall energy level, peak/low hours, and provides a suggestion.
    """
    if date is None:
        date = datetime.now().strftime("%Y-%m-%d")

    service = InsightsService(db)
    prediction = service.get_energy_prediction(date)

    return EnergyPrediction(
        overall=prediction.get('overall', 5),
        peak_hours=prediction.get('peak_hours', []),
        low_hours=prediction.get('low_hours', []),
        suggestion=prediction.get('suggestion', '')
    )


@router.get("/insights/weekly", response_model=Optional[InsightResponse])
async def get_weekly_review(
    week_ending: Optional[str] = Query(None, description="Last day of week (YYYY-MM-DD)"),
    generate: bool = Query(False, description="Generate if not exists"),
    db: Session = Depends(get_db)
):
    """Get or generate weekly review."""
    if week_ending is None:
        week_ending = datetime.now().strftime("%Y-%m-%d")

    service = InsightsService(db)

    if generate:
        insight = service.generate_weekly_review(week_ending)
    else:
        insight = db.query(Insight).filter(
            Insight.date == week_ending,
            Insight.type == "weekly_review"
        ).first()

    if not insight:
        return None

    return InsightResponse(
        id=insight.id,
        type=insight.type,
        date=insight.date,
        content=insight.content,
        confidence=insight.confidence,
        created_at=insight.created_at.isoformat()
    )


@router.get("/insights/recent", response_model=List[InsightResponse])
async def get_recent_insights(
    days: int = Query(7, ge=1, le=30, description="Days to look back"),
    types: Optional[str] = Query(None, description="Comma-separated types to filter"),
    db: Session = Depends(get_db)
):
    """Get recent insights."""
    service = InsightsService(db)

    type_list = types.split(",") if types else None
    insights = service.get_recent_insights(days=days, types=type_list)

    return [
        InsightResponse(
            id=i.id,
            type=i.type,
            date=i.date,
            content=i.content,
            confidence=i.confidence,
            created_at=i.created_at.isoformat()
        )
        for i in insights
    ]
