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
from .integrations.oura import OuraSyncService, sync_oura_data


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


class OuraSyncRequest(BaseModel):
    start_date: Optional[str] = None
    end_date: Optional[str] = None


class OuraSyncResultResponse(BaseModel):
    success: bool
    data_type: str
    records_synced: int
    date_range: List[str]
    errors: List[str]


class OuraSyncResponse(BaseModel):
    results: List[OuraSyncResultResponse]
    total_synced: int


class BriefDeliveryRequest(BaseModel):
    date: Optional[str] = None
    channels: Optional[List[str]] = None  # ["telegram", "discord"]
    regenerate: bool = False


class NotifyResultResponse(BaseModel):
    success: bool
    channel: str
    message_id: Optional[str] = None
    error: Optional[str] = None


class BriefDeliveryResponse(BaseModel):
    brief_date: str
    brief_content: str
    notifications: List[NotifyResultResponse]
    all_successful: bool


class NotifyStatusResponse(BaseModel):
    telegram_enabled: bool
    discord_enabled: bool
    enabled_channels: List[str]


class WeeklyReviewDeliveryRequest(BaseModel):
    week_ending: Optional[str] = None
    channels: Optional[List[str]] = None  # ["telegram", "discord"]
    regenerate: bool = False


class PatternSummary(BaseModel):
    name: str
    description: str


class WeeklyReviewDeliveryResponse(BaseModel):
    week_ending: str
    review_content: str
    patterns: List[PatternSummary]
    avg_sleep_hours: Optional[float] = None
    avg_readiness: Optional[int] = None
    notifications: List[NotifyResultResponse]
    all_successful: bool


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
            metadata=d.extra_data or {}
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
            metadata=d.extra_data or {}
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
            metadata=d.extra_data or {}
        )
        for d in data
    ]


# === Oura Sync Endpoints ===

@app.post("/api/oura/sync", response_model=OuraSyncResponse)
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


@app.post("/api/oura/backfill", response_model=OuraSyncResponse)
async def backfill_oura(
    days: int = Query(30, ge=1, le=365, description="Days of history to backfill"),
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


@app.get("/api/oura/status")
async def oura_status():
    """
    Check Oura integration status.

    Returns whether the Oura token is configured.
    """
    from .config import settings

    has_token = bool(settings.oura_token)

    return {
        "configured": has_token,
        "base_url": settings.oura_base_url
    }


# === Notifications ===

@app.get("/api/notify/status", response_model=NotifyStatusResponse)
async def notify_status():
    """
    Check notification configuration status.

    Returns which channels (Telegram, Discord) are configured.
    """
    from .integrations.notify import get_notification_service

    notifier = get_notification_service()

    return NotifyStatusResponse(
        telegram_enabled=notifier.telegram_enabled,
        discord_enabled=notifier.discord_enabled,
        enabled_channels=[c.value for c in notifier.enabled_channels]
    )


@app.post("/api/brief/deliver", response_model=BriefDeliveryResponse)
async def deliver_brief(
    request: BriefDeliveryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and deliver today's brief via Telegram/Discord.

    This is the main endpoint for morning brief delivery.
    Can be called by cron or manually triggered.

    Args:
        date: Date for brief (defaults to today)
        channels: Specific channels to use (defaults to all enabled)
        regenerate: Force regenerate even if brief exists
    """
    from .integrations.notify import get_notification_service, NotifyChannel

    # Get or generate brief
    date = request.date or datetime.now().strftime("%Y-%m-%d")
    service = InsightsService(db)

    if request.regenerate:
        insight = service.force_regenerate("daily_brief", date)
    else:
        insight = service.generate_daily_brief(date)

    if not insight:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate brief - insufficient data"
        )

    # Get sleep and readiness for display
    sleep_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "sleep"
    ).first()
    readiness_dp = db.query(DataPoint).filter(
        DataPoint.date == date,
        DataPoint.type == "readiness"
    ).first()

    sleep_hours = sleep_dp.value if sleep_dp else None
    readiness_score = int(readiness_dp.value) if readiness_dp else None

    # Get notification service
    notifier = get_notification_service()

    if not notifier.enabled_channels:
        raise HTTPException(
            status_code=400,
            detail="No notification channels configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL"
        )

    # Parse requested channels
    channels = None
    if request.channels:
        channels = []
        for ch in request.channels:
            try:
                channels.append(NotifyChannel(ch.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid channel: {ch}. Valid: telegram, discord"
                )

    # Send notifications
    results = notifier.send_brief_sync(
        content=insight.content,
        date=insight.date,
        sleep_hours=sleep_hours,
        readiness_score=readiness_score,
        confidence=insight.confidence,
        channels=channels
    )

    # Build response
    notify_responses = [
        NotifyResultResponse(
            success=r.success,
            channel=r.channel.value,
            message_id=r.message_id,
            error=r.error
        )
        for r in results
    ]

    return BriefDeliveryResponse(
        brief_date=insight.date,
        brief_content=insight.content,
        notifications=notify_responses,
        all_successful=all(r.success for r in results)
    )


@app.post("/api/weekly-review/deliver", response_model=WeeklyReviewDeliveryResponse)
async def deliver_weekly_review(
    request: WeeklyReviewDeliveryRequest,
    db: Session = Depends(get_db)
):
    """
    Generate and deliver weekly review via Telegram/Discord.

    This is the main endpoint for Sunday evening delivery.
    Can be called by cron or manually triggered.

    Args:
        week_ending: End date of the week (defaults to today)
        channels: Specific channels to use (defaults to all enabled)
        regenerate: Force regenerate even if review exists
    """
    from .integrations.notify import get_notification_service, NotifyChannel
    from .models import Pattern

    # Get or generate weekly review
    week_ending = request.week_ending or datetime.now().strftime("%Y-%m-%d")
    service = InsightsService(db)

    # Run pattern detection first
    patterns = service.detect_patterns(days=30, force=request.regenerate)

    if request.regenerate:
        insight = service.force_regenerate("weekly_review", week_ending)
    else:
        insight = service.generate_weekly_review(week_ending)

    if not insight:
        raise HTTPException(
            status_code=500,
            detail="Failed to generate weekly review - insufficient data"
        )

    # Calculate week averages
    end_date = datetime.strptime(week_ending, "%Y-%m-%d")
    start_date = end_date - timedelta(days=6)

    sleep_data = db.query(DataPoint).filter(
        DataPoint.type == "sleep",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    readiness_data = db.query(DataPoint).filter(
        DataPoint.type == "readiness",
        DataPoint.date >= start_date.strftime("%Y-%m-%d"),
        DataPoint.date <= week_ending
    ).all()

    avg_sleep = None
    if sleep_data:
        sleep_values = [dp.value for dp in sleep_data if dp.value is not None]
        if sleep_values:
            avg_sleep = sum(sleep_values) / len(sleep_values)

    avg_readiness = None
    if readiness_data:
        readiness_values = [dp.value for dp in readiness_data if dp.value is not None]
        if readiness_values:
            avg_readiness = int(sum(readiness_values) / len(readiness_values))

    # Get notification service
    notifier = get_notification_service()

    if not notifier.enabled_channels:
        raise HTTPException(
            status_code=400,
            detail="No notification channels configured. Set TELEGRAM_BOT_TOKEN + TELEGRAM_CHAT_ID or DISCORD_WEBHOOK_URL"
        )

    # Parse requested channels
    channels = None
    if request.channels:
        channels = []
        for ch in request.channels:
            try:
                channels.append(NotifyChannel(ch.lower()))
            except ValueError:
                raise HTTPException(
                    status_code=400,
                    detail=f"Invalid channel: {ch}. Valid: telegram, discord"
                )

    # Build pattern dicts for notification
    pattern_dicts = [
        {"name": p.name, "description": p.description}
        for p in patterns if p.actionable
    ]

    # Send notifications
    results = notifier.send_weekly_review_sync(
        content=insight.content,
        week_ending=insight.date,
        avg_sleep_hours=avg_sleep,
        avg_readiness=avg_readiness,
        patterns=pattern_dicts,
        confidence=insight.confidence,
        channels=channels
    )

    # Build response
    notify_responses = [
        NotifyResultResponse(
            success=r.success,
            channel=r.channel.value,
            message_id=r.message_id,
            error=r.error
        )
        for r in results
    ]

    pattern_summaries = [
        PatternSummary(name=p.name, description=p.description)
        for p in patterns if p.actionable
    ]

    return WeeklyReviewDeliveryResponse(
        week_ending=insight.date,
        review_content=insight.content,
        patterns=pattern_summaries,
        avg_sleep_hours=avg_sleep,
        avg_readiness=avg_readiness,
        notifications=notify_responses,
        all_successful=all(r.success for r in results)
    )


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
        extra_data={
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
