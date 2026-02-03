"""
LifeOS API Server

FastAPI endpoints for the LifeOS system.
"""

from datetime import datetime, timedelta
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from .config import settings
from .database import get_db, init_db
from .models import DataPoint, Insight, Pattern, JournalEntry, Task, Note
from .insights_service import InsightsService
from .integrations.capture import CaptureService, process_webhook, CaptureType


# === Pydantic Models ===

class HealthResponse(BaseModel):
    status: str
    version: str
    timestamp: str


class InsightResponse(BaseModel):
    id: int
    type: str
    date: str
    content: str
    confidence: float
    created_at: str

    class Config:
        from_attributes = True


class PatternResponse(BaseModel):
    id: int
    name: str
    description: str
    pattern_type: str
    variables: List[str]
    strength: float
    confidence: float
    sample_size: int
    actionable: bool

    class Config:
        from_attributes = True


class EnergyPrediction(BaseModel):
    overall: int
    peak_hours: List[str]
    low_hours: List[str]
    suggestion: str


class GenerateRequest(BaseModel):
    insight_type: str
    date: Optional[str] = None


class LogEnergyRequest(BaseModel):
    energy: int  # 1-5
    mood: Optional[int] = None  # 1-5
    notes: Optional[str] = None


class DataPointResponse(BaseModel):
    id: int
    source: str
    type: str
    date: str
    value: Optional[float]
    metadata: dict

    class Config:
        from_attributes = True


class CaptureRequest(BaseModel):
    text: str
    source: Optional[str] = "manual"


class WebhookPayload(BaseModel):
    text: str
    source: Optional[str] = "webhook"
    user_id: Optional[str] = None
    timestamp: Optional[str] = None
    chat_id: Optional[str] = None
    message_id: Optional[str] = None


class CaptureResponse(BaseModel):
    type: str
    success: bool
    message: str
    data: dict


class TaskResponse(BaseModel):
    id: int
    title: str
    description: Optional[str]
    status: str
    priority: str
    due_date: Optional[str]
    tags: List[str]
    source: str
    created_at: str

    class Config:
        from_attributes = True


class NoteResponse(BaseModel):
    id: int
    title: Optional[str]
    content: str
    tags: List[str]
    source: str
    created_at: str

    class Config:
        from_attributes = True


# === FastAPI App ===

app = FastAPI(
    title="LifeOS",
    description="AI-powered personal operating system. Passive capture, active insights.",
    version="0.1.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"]
)


# === Startup ===

@app.on_event("startup")
async def startup():
    """Initialize database on startup."""
    init_db()


# === Health ===

@app.get("/api/health", response_model=HealthResponse)
async def health():
    """Health check endpoint."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        timestamp=datetime.utcnow().isoformat()
    )


# === Insights Endpoints ===

@app.get("/api/insights/brief", response_model=Optional[InsightResponse])
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


@app.get("/api/insights/patterns", response_model=List[PatternResponse])
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


@app.post("/api/insights/detect-patterns", response_model=List[PatternResponse])
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


@app.post("/api/insights/generate", response_model=InsightResponse)
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


@app.get("/api/predictions/energy", response_model=EnergyPrediction)
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


@app.get("/api/insights/weekly", response_model=Optional[InsightResponse])
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


@app.get("/api/insights/recent", response_model=List[InsightResponse])
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


# === Data Endpoints ===

@app.get("/api/data/sleep", response_model=List[DataPointResponse])
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
            metadata=d.metadata or {}
        )
        for d in data
    ]


@app.get("/api/data/readiness", response_model=List[DataPointResponse])
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
            metadata=d.metadata or {}
        )
        for d in data
    ]


@app.get("/api/data/activity", response_model=List[DataPointResponse])
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
            metadata=d.metadata or {}
        )
        for d in data
    ]


# === Quick Capture ===

@app.post("/api/log")
async def log_energy(
    request: LogEnergyRequest,
    db: Session = Depends(get_db)
):
    """
    Quick log energy/mood.

    Minimal friction capture for current state.
    """
    now = datetime.now()
    date = now.strftime("%Y-%m-%d")
    time = now.strftime("%H:%M")

    entry = JournalEntry(
        date=date,
        time=time,
        energy=request.energy,
        mood=request.mood,
        notes=request.notes
    )
    db.add(entry)

    # Also store as data point for pattern analysis
    dp = DataPoint(
        source="manual",
        type="energy",
        date=date,
        value=request.energy,
        metadata={
            "time": time,
            "mood": request.mood,
            "notes": request.notes
        }
    )
    db.add(dp)

    db.commit()

    return {
        "success": True,
        "date": date,
        "time": time,
        "energy": request.energy
    }


@app.post("/api/capture", response_model=CaptureResponse)
async def capture_message(
    request: CaptureRequest,
    db: Session = Depends(get_db)
):
    """
    Quick capture with AI categorization.

    Accepts free-form text, uses AI to categorize as note/task/energy,
    and stores appropriately.
    """
    service = CaptureService(db)
    result = service.process(
        text=request.text,
        source=request.source or "manual"
    )

    return CaptureResponse(
        type=result.type.value,
        success=result.success,
        message=result.message,
        data=result.data
    )


@app.post("/api/webhook/clawdbot", response_model=CaptureResponse)
async def clawdbot_webhook(
    payload: WebhookPayload,
    db: Session = Depends(get_db)
):
    """
    Webhook endpoint for Clawdbot (Telegram/Discord).

    Receives messages and processes them through the capture system.
    """
    result = process_webhook(db, payload.model_dump())

    return CaptureResponse(
        type=result.type.value,
        success=result.success,
        message=result.message,
        data=result.data
    )


@app.get("/api/tasks", response_model=List[TaskResponse])
async def get_tasks(
    status: Optional[str] = Query(None, description="Filter by status"),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get tasks, optionally filtered by status."""
    query = db.query(Task)

    if status:
        query = query.filter(Task.status == status)

    tasks = query.order_by(Task.created_at.desc()).limit(limit).all()

    return [
        TaskResponse(
            id=t.id,
            title=t.title,
            description=t.description,
            status=t.status,
            priority=t.priority,
            due_date=t.due_date,
            tags=t.tags or [],
            source=t.source,
            created_at=t.created_at.isoformat()
        )
        for t in tasks
    ]


@app.get("/api/notes", response_model=List[NoteResponse])
async def get_notes(
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db)
):
    """Get recent notes."""
    notes = db.query(Note).order_by(Note.created_at.desc()).limit(limit).all()

    return [
        NoteResponse(
            id=n.id,
            title=n.title,
            content=n.content,
            tags=n.tags or [],
            source=n.source,
            created_at=n.created_at.isoformat()
        )
        for n in notes
    ]


@app.get("/api/today")
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
            "score": sleep.metadata.get('score') if sleep and sleep.metadata else None,
            "deep_sleep_hours": sleep.metadata.get('deep_sleep_hours') if sleep and sleep.metadata else None
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


# === Static Files & Frontend ===

import os
from pathlib import Path

# Determine UI directory (works in both local dev and Docker)
_ui_dir = Path(__file__).parent.parent / "ui"
if not _ui_dir.exists():
    _ui_dir = Path("/app/ui")

if _ui_dir.exists():
    # Serve static assets (CSS, JS)
    app.mount("/static", StaticFiles(directory=str(_ui_dir)), name="static")

    @app.get("/")
    async def serve_index():
        """Serve the main dashboard."""
        return FileResponse(str(_ui_dir / "index.html"))

    @app.get("/{path:path}")
    async def serve_static(path: str):
        """Serve static files or fallback to index for SPA routing."""
        file_path = _ui_dir / path
        if file_path.exists() and file_path.is_file():
            return FileResponse(str(file_path))
        return FileResponse(str(_ui_dir / "index.html"))


# === Run Server ===

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host=settings.host, port=settings.port)
